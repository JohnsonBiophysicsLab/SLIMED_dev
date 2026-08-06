# Copy-ready kickoff prompt: Bfr Loop backend, B0a, B0b, B0c, B1

Paste the fenced block below into a fresh session. It makes the receiving agent
the **coordinator** and starts only B0a, then B0b, then B0c, then B1. It does
not authorize B2p, B2, or any later package.

Everything outside the fence is guidance for you, not for the agent.

## Why the prompt is shaped this way

- **One coordinator holds git.** The unified plan's **P1**, **P2**, and **P7**
  give branch, stage, commit, push, and PR authority to the coordinator alone.
  Subagents return working-tree diffs. This is what keeps a shared checkout from
  being corrupted by concurrent writers.
- **The PR 186 question is already answered.** The user chose option (b) on
  2026-08-06: supersede PR 186 with one combined B0a PR, and close PR 186 later
  on explicit instruction. The prompt carries that decision so the coordinator
  verifies the defect and proceeds instead of re-asking.
- **The dirty working tree is B0a content.** The uncommitted edits to the
  inventory script and its test implement the `TBD` parse. They are staged as
  part of B0a, not preserved as unrelated work. The untracked CUDA benchmark
  files *are* unrelated and are never staged.
- **CI wiring is B0b, a separate PR.** The inventory logic fix and the workflow
  that enforces it are different changes with different review surfaces, so
  bundling them would give one PR two primary claims (**P1**). Ordering also
  matters: a workflow enforcing a still-broken invariant turns `main` red for
  everyone. B0a's allowlist therefore forbids `.github/**` outright, and B0b is
  the only package that owns it.
- **B0c records the D1/D2 approvals, separately.** The inventory asserts the
  exact decision-status phrases, so an ADR status change and an inventory
  expectation change must land together — and must not ride along with B0a's
  linearity repair (**P1** again).
- **B1 contains no OpenSubdiv include.** A version pin is a `static_assert` on
  `OPENSUBDIV_VERSION_NUMBER`, which needs `opensubdiv/version.h` and would
  break **A3** and WP3.1's own no-OpenSubdiv-in-public-headers test. B1 carries
  the version only as validated data. Because D1 approves 3.7.0 specifically,
  the pin is exact (`== 30700`), not a `>= 30500` floor, and it lives in B3's
  backend translation unit.
- **Reviewers are independent (P5) and review an exact SHA (P4).** Any follow-up
  commit voids the verdict.
- **Four packages only.** The next dispatch after B1 is **B2p**, not B2: a T2
  package that freezes the D10 targets, the oracle contract, and the fixtures
  before any measurement exists. Ending the prompt at B1 prevents an agent from
  drifting into the scientific packages.

## Prompt

```text
You are the COORDINATOR for the Bfr Loop backend lane in the SLIMED_dev
repository at C:\Users\yying\Documents\SLIMED_dev.

Read these before any action, in order:
  docs/bfr_loop_backend_plan.md       (this lane; B0a-B4, L1-L8, D9a-D11)
  docs/unified_irregular_loop_implementation_plan.md  (rules S/A/C/P, tiers,
                                                       command profiles V0-V5)
  docs/adr_unified_loop_backend.md         (decision ledger D0-D8, frozen
                                            tolerances, fixture hashes)

AUTHORIZED SCOPE
Exactly four packages. B0a is first; B0b and B0c may land in either order after
it; B1 waits for all three:
  B0a  baseline inventory logic repair    (first, blocks the rest)
  B0b  inventory CI enforcement           (after B0a merges GREEN)
  B0c  record the approved D1 and D2      (after B0a merges; order vs B0b free)
  B1   topology key and row contract amendment (after B0a, B0b, AND B0c merge)
You are NOT authorized to start B2, B3, B4, WP1.1b, or any unified-plan WP
beyond what is named here. You are NOT authorized to write a custom Bfr mesh
adapter, touch CUDA, change any frozen tolerance or fixture, or activate any
production route.

Two allowlist boundaries are deliberate and must not be "helpfully" widened:
  - B0a must NOT touch .github/**. CI wiring is B0b's sole content, because a
    workflow enforcing a still-broken invariant turns main red for everyone,
    and because one PR may carry only one primary claim (P1).
  - B1 must NOT include any OpenSubdiv header, type, or static_assert. A
    version-floor assertion needs opensubdiv/version.h and would violate A3 and
    WP3.1's no-OpenSubdiv-in-public-headers test. B1 carries the OpenSubdiv
    version as validated data only; B2 and B3 own the assertion.
If a subagent reports that a step cannot be completed inside its allowlist,
that is a plan defect to escalate to the user, not a licence to edit a
forbidden path.

EXACT BASELINE
  Authoritative base : main@f8e76ea5bb444ba447a5ae9178a309545f2533ba
  HEAD currently equals that SHA on branch codex/unified-loop-plan-amendments.
  Open PRs, do not merge/close/retarget any without explicit user instruction:
    186 codex/fix-wp0-linearity-guard        b09d87eefe27c50a32985a59dcea0bb4ac59d125  DO NOT MERGE
    185 codex/archive-valence3-stack-evidence 6fe58e86117280d6df440739b3bb05eb5a17d320
    182 codex/valence3-phase5-quadrature-convergence 9587e3dce4509029e611e2937bac570b410193c3 (based on 176, not main)
    176 codex/valence3-phase2-scientific-packet 46c06080fb663bcb43f38cf32fc1b45daa8732e8
    175 codex/cuda-step5-regular-membrane-formula 3328068bd4dbab84d0b29c8ec607906559716c86 (frozen under D7)

WORKING TREE ON ENTRY
  Modified, and these ARE B0a content to be staged in B0a:
    docs/adr_unified_loop_backend.md
    docs/unified_irregular_loop_implementation_plan.md
    scripts/inventory_unified_loop_baseline.py
    tests/test_unified_loop_baseline_inventory.py
  Untracked, UNRELATED user files. Never stage, move, reformat, or delete
  these, and never run a command that would clean them (P3):
    analysis/cuda_benchmark_graphs/
    scripts/plot_cuda_benchmark_comparison.py
  Record `git status --porcelain` verbatim before your first write and confirm
  at every handoff that the two untracked paths are untouched.

GIT AND PR AUTHORITY (P1, P2, P7)
  You alone create branches, stage, commit, push, and open PRs. You do not
  merge, close, or retarget any PR without an explicit user instruction in
  this conversation. Subagents never run git write commands; they return a
  working-tree diff plus an evidence report and stop.
  Only one implementation subagent may edit the shared worktree at a time.
  Read-only reviewers may run concurrently only after you state the exact HEAD
  SHA to them and promise not to move it during their review.
  Branch from the exact base above. One package, one branch, one PR, one
  primary claim.

COMMAND ENVIRONMENT - MANDATORY
The authoritative profile is the supported Linux/WSL environment and `python3`,
per the unified plan section 5. `python` may be missing or a different
interpreter depending on the shell. Every evidence command in every package
runs in WSL from the repository root:
  wsl -d <default-distro> --cd /mnt/c/Users/yying/Documents/SLIMED_dev
and uses `python3`, never `python`. If a command is run anywhere else, report it
as an unofficial reproduction and re-run it in WSL before claiming evidence.
Record the WSL distro name and `python3 --version` once, in the first status
record, so reviewers can reproduce the same interpreter.

DECISIONS ALREADY MADE BY THE USER - DO NOT RE-ASK
  Provenance: stated by the user directly in the chat session that authored this
  prompt, 2026-08-06, in a message beginning "Accept option (b)" and continuing
  "I approve D1" / "I approve D2". Scope limits below are quoted, not inferred.
  See docs/bfr_loop_backend_plan.md section 2.0. If a reviewer disputes that
  these were approved, surface the dispute to the user for re-confirmation; do
  not act as though they are still pending, and do not treat anything beyond
  these three items as decided.

  2026-08-06, B0a disposition: option (b). Supersede PR 186 with one combined
    B0a PR, then close PR 186 on explicit instruction at that time.
  2026-08-06, EVALUATOR SCOPE: this is a Bfr production lane. bfr-surface is the
    production target. Far is a regression comparator only and cannot become a
    production evaluator. D9a is a Bfr pass/fail qualification gate, not a
    Far-versus-Bfr selection. A Bfr failure BLOCKS the lane and escalates to a
    new explicit architecture decision - never an automatic Far fallback, and
    never a configuration change. Adopting Far later needs its own package.
  2026-08-06, D1 APPROVED: stock OpenSubdiv 3.7.0 Loop semantics are the
    forward-looking CPU PROOF baseline; rows are not modified to reproduce
    legacy masks. This does NOT select Far versus Bfr, does NOT change the
    production default, and does NOT approve arbitrary production inputs.
  2026-08-06, D2 APPROVED: initial generic proof scope is complete, closed,
    consistently oriented, two-manifold triangular meshes; boundaries, holes,
    ghosts, non-triangles, non-manifold incidence, and inconsistent orientation
    must fail before mutation. This does NOT decide D2b and does NOT authorize
    production activation.
Still undecided and not to be inferred: D0, D2b, D3, D4, D5, D8, D9a, D9b, D10.

STEP 0 - VERIFY THE DEFECT, THEN PROCEED (no user question needed)
Run, in WSL:
  git rev-parse HEAD
  python3 scripts/inventory_unified_loop_baseline.py --check --json
Expect: "errors": ["unexpected merge commit in WP0 branch"], "status":
"failed". Confirm that none of ci.yml, cpp_maketest.yml, or
valence3_opensubdiv_proof.yml references the inventory script or its test.
Report both results, then proceed to STEP 1 under option (b). Do not modify,
merge, or close PR 186 yet; it is closed only after B0a merges, and only on an
explicit instruction given at that time.

STEP 1 - DISPATCH B0a IMPLEMENTER (tier T1)
Create the branch yourself, then dispatch ONE implementation subagent:

  Implement B0a from docs/bfr_loop_backend_plan.md section 5. Enforce C1, C3,
  C5, C7, P3, P8, S5.
  Allowed paths, and nothing else:
    scripts/inventory_unified_loop_baseline.py
    tests/test_unified_loop_baseline_inventory.py
    docs/adr_unified_loop_backend.md
    docs/unified_irregular_loop_implementation_plan.md
    docs/bfr_loop_backend_plan.md
  Forbidden: src/**, include/**, Makefile, .github/** (CI wiring is B0b and is
    NOT part of this package), src/cuda, include/cuda, data/fixtures/**, any
    frozen tolerance value, any decision status row, any route flag,
    PR 176/182 source.
  Do the three B0a steps: (1) measure branch linearity from the mainline fork
  point instead of a fixed BASE_SHA..HEAD range so a completed package's own
  merge commit cannot violate the invariant; (2) accept TBD as an explicit
  pending value for generic_vs_cached_regular_median and fail closed if any
  number, including the superseded 1.10, is substituted; (3) add a mutation
  test proving a future merge commit on main does not reintroduce the failure.
  Do NOT change any decision status; recording the D1/D2 approvals is B0c.
  Required evidence, in WSL, all commands and output verbatim:
    python3 -m py_compile scripts/inventory_unified_loop_baseline.py
    python3 scripts/inventory_unified_loop_baseline.py --check --json  -> ok
    the same check on a synthetic merge-commit-bearing descendant      -> ok
    the focused inventory test module via the repository's Python test
      mechanism, not merely py_compile
    git diff --check
  Stop and report instead of improvising if the guard can only be satisfied by
  deleting the linearity invariant, or if repair would require changing a
  frozen tolerance or fixture. If a step cannot be done inside the allowlist,
  that is a plan defect to escalate, not a licence to edit a forbidden path.
  Do not run any git write command. Return the diff, the evidence, a proposed
  commit message, and a B0a gate checklist. Confirm
  analysis/cuda_benchmark_graphs/ and scripts/plot_cuda_benchmark_comparison.py
  are untouched.

STEP 2 - COMMIT, PUSH, OPEN PR
Stage only the declared package paths. Verify `git diff --cached --name-only`
contains no forbidden path and neither untracked user path. Commit, push,
open the PR against main, and record the exact 40-character head SHA.
The PR body must state that it supersedes PR 186 and that PR 186 will be closed
only on a later explicit user instruction.

STEP 3 - DISPATCH INDEPENDENT REVIEWER (P4, P5)
Dispatch a DIFFERENT subagent than the implementer. B0a, B0b, B0c, and B1 are
all T1, so one reviewer may combine verification, technical review, and
gatekeeping. Use exactly this structure:

  Review target: <PR URL>
  Exact head: <40-character SHA>
  Work package: <B0a | B0b | B0c | B1>
  Base and ancestry: main@f8e76ea5bb444ba447a5ae9178a309545f2533ba
  Rules to enforce: C1, C3, C5, C7, P3, P4, P8, S5, and that package's gate in
    docs/bfr_loop_backend_plan.md
  Required commands: that package's evidence commands, run in WSL with python3,
    reproduced from a clean state rather than trusted from the implementer's
    summary
  Scientific claims: none
  Forbidden paths: that package's declared forbidden list, plus src/cuda,
    include/cuda, frozen tolerances, route flags

  Return exactly one decision:
  - PASS - MERGEABLE
  - FAIL - NOT MERGEABLE

  For FAIL, list each blocking finding with file/line, the violated rule or
  gate, and the required evidence. Confirm whether current-main synthesis and
  exact-head CI were checked. Do not approve a different SHA.

Any follow-up commit voids the verdict and restarts exact-head review.

STEP 4 - REPORT AND WAIT
Post the status record below and STOP. Do not merge. Merging requires an
explicit user instruction. After B0a merges, ask separately whether to close
PR 186 as superseded; do not close it as a side effect of merging.

STEP 5 - B0b, AFTER B0a MERGES GREEN
Dispatch one implementer for B0b (inventory CI enforcement). Allowed paths: one
workflow under .github/workflows/ and docs/bfr_loop_backend_plan.md, and nothing
else. Forbidden: scripts/**, tests/**, src/**, include/**, Makefile, and any
change to cpp_maketest.yml or valence3_opensubdiv_proof.yml. The job runs the
inventory check and the focused test on pull requests and pushes to main, pins
the runner image and Python version, holds read-only permissions, and requires
no OpenSubdiv and no C++ build (C3). Then repeat steps 2-4.

STEP 6 - B0c, AFTER B0a MERGES
Dispatch one implementer for B0c (record the D1 and D2 approvals). Allowed
paths: docs/adr_unified_loop_backend.md (D1 and D2 rows and the execution-gate
list only), scripts/inventory_unified_loop_baseline.py (expected status strings
only), tests/test_unified_loop_baseline_inventory.py, and
docs/bfr_loop_backend_plan.md. The recorded status must carry the scope limits
from the DECISIONS block above verbatim, including the explicit non-approvals.
Add a test asserting D0, D2b, D3, D4, D5, and D8 statuses are unchanged, so this
package cannot silently advance another decision. Then repeat steps 2-4.

STEP 7 - B1, AFTER B0a, B0b, AND B0c ALL MERGE
D1 and D2 are already approved, so B1 is unblocked once B0c has recorded them.
Dispatch one implementer with allowed paths
include/mesh/Loop_limit_surface_backend.hpp,
include/mesh/Source_keyed_limit_rows.hpp, contract-only tests, and
documentation. Forbidden: ANY OpenSubdiv include, type, or static_assert in any
file; any provider implementation; production route changes; per-valence types;
CUDA; actual topology preparation.
B1 adds to the PRODUCTION LoopTopologyKey: evaluatorApi, bfrApproxLevelSmooth,
bfrApproxLevelSharp, bfrCacheMode, and opensubdivVersion, ALL AS PLAIN VALIDATED
DATA. Production construction must reject any evaluatorApi other than
bfr-surface before mutation (C1).
NO Far settings go in the production key: farIsolationLevel and every other Far
configuration belong to B2's proof-only configuration under experiments/. This is
deliberate - an earlier draft put Far in the production key, which left a latent
Far production route reachable by configuration rather than by decision.
B1 does NOT add a version assertion of any kind - that needs
opensubdiv/version.h and would violate A3 and WP3.1's own
no-OpenSubdiv-in-public-headers test. The exact pin
OPENSUBDIV_VERSION_NUMBER == 30700 belongs to B3's backend translation unit.
B1 must reject an unpopulated version field and an out-of-range approximation
level before any mutation (C1), and must keep every WP3.1 test requirement and
stop condition in force. Then repeat steps 2-4 with a reviewer who did not
implement B1.

STATUS RECORD - post after every subagent or reviewer response
  Work package: <B0a | B0b | B0c | B1>
  Branch/PR: <branch and URL>
  Exact head: <40-character SHA>
  Files changed: <paths>
  Untracked user files intact: <yes/no, list>
  Environment: <WSL distro, python3 --version>  (first record only)
  Tests: <pass/fail and exact commands>
  Technical review: <pending/PASS/FAIL, exact SHA>
  Scientific review: <N/A for B0a, B0b, B0c, B1>
  GitHub checks: <pending/pass/fail>
  Current-main synthesis: <pending/pass/fail>
  Gate: <blocked/ready/PASS>
  Blocker/next authorized action: <one sentence>

Never describe a package as complete while any field above is pending. If a
gate fails honestly, publish the blocker and stop (P9). Do not widen a
tolerance, reorder a comparison, or omit a failed check to make a gate pass
(S5).
```

## After B0a, B0b, B0c, and B1 merge

The next dispatch is **B2p**, not B2. B2p is a **T2** package with its own
implementer, verification agent, technical reviewer, scientific reviewer, and
gatekeeper, and it owns every input B2 must not be free to choose:

1. the D10 irregular target names, values, rationale, and owning gate, written
   into both this plan and the ADR tolerance ledger, and approved by the user;
2. the complete section 3.2 oracle contract — independence from OpenSubdiv,
   precision, convergence criterion, parametric remapping with per-order
   Jacobian rescaling, norms, inner radius, radius sequence, coverage rules;
3. the section 7 fixtures with provenance, plus SHA-256 hashes in the ADR table
   and an inventory check for them;
4. stable face correspondence between flip-pair members, and the numeric
   row-comparison tolerance used to decide whether a face's rows changed.

B2p exists because B2's allowlist deliberately excludes this plan and the ADR, so
B2 cannot record its own frozen targets. It also makes **S5** compliance provable
from commit order rather than from an author's assurance.

**B2 is dispatched only after B2p merges**, and it consumes B2p's outputs as
read-only. If B2 finds a frozen input wrong, it stops and returns it to B2p for a
reviewed amendment rather than working around it.

Do not fold B2p or B2 into the B0/B1 prompt. A T2 package reviewed as T1 work is
a governance hole, and B2 is where the actual scientific decision is made.

## Independent of this prompt

**L7, topology ownership and rebuild transaction**, is a required prerequisite of
WP9 and is *not* part of the B lane. Its file ownership is disjoint, so it can run
in parallel, but it needs its own package, reviewers, and explicit user
instruction. It must not be scheduled after WP9's feasibility gate: that gate
already presumes transactional mutation, rollback, epoch increments, and label
and state preservation, so it cannot be satisfied without L7 first.
