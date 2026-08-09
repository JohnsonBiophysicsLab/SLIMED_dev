# Bfr Loop limit-surface backend plan (macOS)

Status: draft, non-authorizing. No package below is authorized to start.

Date: 2026-08-06

Authoritative base: `main@f8e76ea5bb444ba447a5ae9178a309545f2533ba`

## 1. Purpose and relationship to the existing plan

This document adds one evaluator-selection lane and one legacy-disposition
lane to the existing programme. It does **not** replace
[`unified_irregular_loop_implementation_plan.md`](unified_irregular_loop_implementation_plan.md)
(the "unified plan") or
[`adr_unified_loop_backend.md`](adr_unified_loop_backend.md) (the "ADR").

Division of authority between the documents:

| Concern | Owning document |
| --- | --- |
| Rules S1-S7, A1-A9, C1-C7, P1-P10 | unified plan section 3 |
| Decisions D0-D8 | ADR decision ledger |
| Package lifecycle, command profiles V0-V5, review tiers | unified plan sections 4-5 |
| Frozen tolerance and fixture ledger | ADR |
| Bfr evaluator qualification and activation/readiness | **this document**, D9a-D12 |
| Legacy stratum disposition | **this document**, section 6 |
| Face kernel, quadrature, shadow route, production, CUDA | unified plan WP4-WP8 |

Rules are cited by ID and never restated here. Where this document replaces a
unified-plan package it says so explicitly; every other unified-plan package
remains in force unchanged.

**Rationale.** The unified plan commits WP3.2 to the Far pipeline
(`TopologyRefiner` -> adaptive refinement -> `PatchTable` ->
`LimitStencilTableFactory` -> source-keyed rows). OpenSubdiv 3.5 introduced
`Bfr`, whose `Surface<double>::EvaluateStencil()` returns position, first, and
both pure plus mixed second-derivative stencils keyed by original mesh vertex
indices, with no patch table, stencil table, or Ptex coordination. That maps
almost exactly onto the WP3.1 six-row contract.

Per the user decision of 2026-08-06, **`bfr-surface` is the production target for
the generic backend** and Far is retained only as a regression comparator and
proof-time cross-check. That is a scope decision, not an evidence-free
assumption: Bfr must still pass its own qualification gate before any production
code is written, and a Bfr failure blocks the lane rather than silently falling
back to Far. Far and Bfr are two different approximations of the irregular Loop
limit surface, so qualifying Bfr is a scientific act requiring its own evidence
and gate.

## 2. Current state of the world

Exact references. Any change invalidates the packages below.

| Object | Exact reference | State |
| --- | --- | --- |
| Authoritative base | `f8e76ea5bb444ba447a5ae9178a309545f2533ba` | merged PR 184 |
| Prior ADR base | `e9af3ddad494fc073040ee82bdf07944b9fee8cf` | merged PR 183 |
| PR 175 CUDA Step 5 | `3328068bd4dbab84d0b29c8ec607906559716c86` | open, frozen under D7 |
| PR 176 Valence-3 stack root | `46c06080fb663bcb43f38cf32fc1b45daa8732e8` | open, production code |
| PR 182 Valence-3 evidence leaf | `9587e3dce4509029e611e2937bac570b410193c3` | open, stacked on PR 176 |
| PR 185 fixture archive | `6fe58e86117280d6df440739b3bb05eb5a17d320` | open, D0 extraction |
| PR 186 linearity guard fix | `b09d87eefe27c50a32985a59dcea0bb4ac59d125` | open; user chose option (b): superseded by B0a, close on instruction |

### 2.0 Decisions resolved since the ADR was written

**Provenance.** The three items below were stated by the user directly in the
chat session that authored this plan, on 2026-08-06, in a message beginning
"Accept option (b)" and continuing "I approve D1" and "I approve D2". The scope
limits are quoted from that message, not paraphrased. A reviewer who cannot see
that session should treat this subsection as the citation and ask the user to
re-confirm rather than assume inference; a reviewer must not silently downgrade
these to pending.

A **fourth** decision was taken in the same session later that day, after an
external review recommended it: this is a **Bfr production lane**. D9a is a Bfr
qualification gate rather than a Far-versus-Bfr selection, Far cannot be admitted
as a production evaluator, and adopting Far later would require a new explicit
architecture decision and package rather than a configuration change. This is
compatible with D1's "does not select Far versus Bfr" limit: D1 governs the
*scheme*, and the evaluator scope was set separately and explicitly.

Nothing beyond these four items was approved.

The approvals are recorded in the ADR by B0c; until B0c merges, the ADR still
reads "proposed" and the inventory still expects that phrasing.

- **D1 approved**: stock OpenSubdiv 3.7.0 Loop semantics are the forward-looking
  CPU **proof** baseline; rows are not modified to reproduce legacy masks. Does
  not select Far versus Bfr, does not change the production default, does not
  approve arbitrary production inputs.
- **D2 approved**: initial generic proof scope is complete, closed, consistently
  oriented, two-manifold triangular meshes; boundaries, holes, ghosts,
  non-triangles, non-manifold incidence, and inconsistent orientation fail before
  mutation. Does not decide D2b, does not authorize production activation.

D1's approval makes the OpenSubdiv version pin **exactly 3.7.0**, not a `>= 3.5`
availability floor. D2's approval sets B2p's fixture generation scope: every new
fixture must be closed, oriented, and two-manifold, and the rejection fixtures
exist to prove failure before mutation.

### 2.1 Blocking defect: main fails its own inventory

At the authoritative base:

```text
python3 scripts/inventory_unified_loop_baseline.py --check --json
-> "errors": ["unexpected merge commit in WP0 branch"], "status": "failed"
```

The linearity guard counts merge commits in `BASE_SHA..HEAD`. PR 184 advanced
`BASE_SHA` to the PR 183 merge, so PR 184's own merge commit now falls inside
the range. The invariant is self-defeating and re-breaks on every future merge.
Every branch cut from main inherits the failure.

A second, independent inconsistency exists in the same files: the ADR now
records `generic_vs_cached_regular_median <= TBD`, while
`scripts/inventory_unified_loop_baseline.py` still expects the numeric `1.10`.

Consequence: **the V0 command profile cannot pass anywhere.** No package in
either document can produce clean evidence until this is repaired. B0a below is
therefore an unconditional prerequisite for every other package here.

The repository has three workflows, `ci.yml`, `cpp_maketest.yml`, and
`valence3_opensubdiv_proof.yml`, and none of them runs
`scripts/inventory_unified_loop_baseline.py` or its focused test. That is why
the defect reached `main` unnoticed. Repairing the logic and closing the CI hole
are two different changes with two different review surfaces, so they are two
packages: B0a and B0b.

### 2.2 Uncommitted working-tree state

The shared checkout carries uncommitted edits to
`docs/adr_unified_loop_backend.md`,
`docs/unified_irregular_loop_implementation_plan.md`,
`scripts/inventory_unified_loop_baseline.py`, and
`tests/test_unified_loop_baseline_inventory.py` that implement the `TBD`
pending-ceiling parse and its mutation tests. This is B0a content, not unrelated
work, and the coordinator dispositions it in B0a.

The untracked `analysis/cuda_benchmark_graphs/` and
`scripts/plot_cuda_benchmark_comparison.py` are unrelated user files. They are
preserved and never staged (**P3**).

## 3. New decisions

These extend the ADR ledger and do not modify D0-D8.

| ID | Status | Proposed rule | Required authority / evidence |
| --- | --- | --- | --- |
| D9a | Proposed - pending B2 evidence and explicit user scientific decision | **Qualify `bfr-surface`.** Pass/fail on Bfr alone: is it scientifically and operationally adequate to carry the generic backend? Far is **not a candidate** and cannot be admitted; it is a regression comparator only. A Bfr failure blocks the lane and escalates to a new explicit architecture decision; there is no automatic Far fallback and no configuration path to one. | B2 evidence, technical review, independent scientific review, explicit user decision. |
| D9b | Deferred - not decidable before WP5.2 | **Bfr production-activation acceptance.** D9a qualifies Bfr's rows; D9b accepts Bfr for production. The deciding quantity is convergence of the integrated bending energy and per-source forces under the *selected* quadrature rule, which does not exist until WP5.2. This is not a Far-versus-Bfr selection. | WP5.2 quadrature selection, then integrated-functional evidence, independent scientific review, and explicit user decision. |
| D10 | Approved - Frozen B2p targets and coverage challenge accepted for B2 proof. This does not qualify Bfr, decide D9a or D9b, widen a target, or authorize production. | Declare frozen irregular row targets. The existing ledger has no irregular accuracy tolerance; `valence{3,4,5}_row_invariants = 1.0e-12` are row sum-rule invariants, not accuracy. | **B2p** declared names, values, rationale, and owning gate before B2 existed, so **S5** compliance is provable from commit order. Explicit user D10 approval on 2026-08-08. Widening after results is a blocker, not a fix. |
| D11 | Proposed - pending explicit user decision after D9a | Legacy per-valence OpenSubdiv routes are frozen as regression comparators, not ported to Bfr, and retired only through the unified plan's WP7 sequence after the generic route is accepted. | Explicit user decision. Extends, and does not replace, D5. |
| D12 | Proposed - pending explicit user approval after technical and scientific review | **Freeze B2 readiness.** Accept the a-priori preparation-cost, retained-row-memory, process-memory, and threading criteria in section 3.4, and accept the complete section-8/section-7 execution manifest and independently generated fixture ledger. | This separate preflight amendment, technical review, independent scientific review, then explicit user approval before any B2 candidate run. Approval changes no D10 input, does not decide D9a or D9b, and does not authorize production. |

Nothing in D9a-D12 may be inferred from D1. D1 governs the *scheme* (stock Loop
masks). D9a and D9b govern whether **Bfr** is qualified to extract rows for that
scheme and then activated in production. A D1 approval is not a D9a approval, and
the 2026-08-06 scope decision that this is a Bfr lane is not a D9a approval
either: it fixes the target, not the evidence.

### 3.1 Why qualification and activation are split, and what B2 can settle

Because Far is not a production candidate, B2 is not a selection study. It is a
Bfr qualification study that uses Far as one of several cross-checks. The
constraints below are why qualification (D9a) and activation (D9b) cannot be
decided together.

**Parity against Far is not a qualification criterion.** OpenSubdiv ships its own Bfr-versus-Far comparison
harness at `regression/bfr_evaluate/` (`bfrSurfaceEvaluator` against
`farPatchEvaluator`, covering catmark, loop, and bilinear, with position, first,
and second derivatives). Its defaults are `relTolerance(0.00005f)` with
`d1Tol = pTol * 5.0` and `d2Tol = d1Tol * 5.0`, relative to bounding-box
extent: roughly `1.25e-3` relative slack on second derivatives, with exact
agreement explicitly not expected. Bending energy is a second-derivative
functional, so a parity test would either fail or be passed by widening a
tolerance, which **S5** forbids.

**Pointwise accuracy at an extraordinary vertex is not a well-posed comparison
either.** The classical Loop limit surface is generally `C^1` but not `C^2` at an
extraordinary vertex, so a unique pointwise second derivative is **not reliably
defined or continuous** there. Whether curvature is bounded is valence- and
eigenstructure-dependent, not universally divergent: with
`rho := |mu| / lambda^2` from the subdivision matrix, principal curvatures tend
to zero for `rho < 1`, diverge for `rho > 1`, and are bounded for `rho = 1` when
`mu` is simple.

An earlier draft of this plan claimed second derivatives are "generally
unbounded" for every `N != 6`. That is too strong and is withdrawn; the correct
statement is that no single pointwise reference value can be claimed, which is
what justifies the inner-radius exclusion regardless of which regime a given
valence falls into.

The same analysis supplies the positive result this plan depends on: Loop's
principal curvatures are **square integrable**, which is precisely the condition
that makes a bending-energy integral well defined even where the pointwise
curvature is not. See
[Reif and Schroder, *Curvature Integrability of Subdivision Surfaces*](https://multires.caltech.edu/pubs/h2.pdf).
That is why the integrated functional, not the pointwise row, is the quantity
that can ultimately discriminate between candidates.

Two consequences follow, and they are the reason a single D9 was over-scoped:

1. the irregular comparison must be reported as a **trend over a sequence of
   radii** approaching the extraordinary vertex, not as one pointwise error;
   and
2. the quantity SLIMED actually consumes is not a row but the **integrated**
   bending energy and per-source forces, which folds in the quadrature rule
   that WP5.1/WP5.2 have not yet selected. Selecting an API on integrated
   evidence before the rule exists would be circular.

**What B2 can therefore settle** — all of it well-posed and none of it
dependent on the unselected quadrature rule:

- **Bfr disqualification.** Failure of the regular `5.0e-6` gate, of the
  `1.0e-12` row sum-rule invariants, of unambiguous original-source
  reconstruction, of internal refinement convergence, or of the preparation
  cost, memory, and threading budgets. These are pass/fail and they decide D9a.
- **Engineering equivalence on the well-posed region.** Position and first
  derivatives, and second derivatives outside a declared radius of any
  extraordinary vertex, against an independent exact oracle.
- **Internal refinement convergence.** For each candidate independently, do its
  own rows converge as its own approximation setting is raised? This needs no
  external oracle, is fully well-posed, and disqualifies a candidate whose rows
  never stabilise.
- **The near-vertex disagreement magnitude, as a measured fact** rather than an
  error: "Far and Bfr differ by X on `duu` within radius r of a valence-N
  vertex at matched preparation cost." This number is an input to WP5.1.
- **Cost, memory, threading, and flip-pair row locality.** Pure engineering.

**What B2 cannot settle**, and must explicitly decline to claim: whether Bfr or
Far is "more accurate" at an extraordinary vertex, and anything requiring the
integrated functional. Production acceptance is D9b, after WP5.2.

### 3.2 The independent oracle

Uniform subdivision alone is an inadequate oracle here. Limit masks give exact
positions and tangents at *vertices*, but SLIMED samples face interiors, and
refining until a vertex lands on a sample point only works for dyadic-rational
parametric coordinates.

B2 therefore uses **Stam's eigenanalysis evaluation of Loop surfaces** as the
primary oracle. It evaluates position, derivatives, and curvature at arbitrary
parameter values for a patch with one isolated extraordinary vertex, by
subdividing in closed form via eigenvalue powers until the sample lies inside a
regular patch whose box-spline evaluation is exact. It is therefore exact for
any parametric location other than the extraordinary vertex itself, which is
precisely the well-posed domain identified above:

- [Jos Stam, *Evaluation of Loop Subdivision Surfaces*](https://www.cs.cmu.edu/afs/cs/academic/class/15456-f15/RelatedWork/Loop-by-Stam.pdf)
- [Persson et al., *On the Use of Loop Subdivision Surfaces for Surrogate Geometry*](https://persson.berkeley.edu/pub/persson06subdiv.pdf)

The oracle is **not** an implementation detail left to B2. The following
contract is frozen by **B2p** before B2 runs, because an oracle specified after
candidate output is visible is not an oracle (**S5**, **S6**). It fixes every
scientific input; B2 remains free only to choose ordinary implementation
mechanics that preserve this contract.

**Independence proof.** The oracle is a separate proof executable whose source,
generated dependency file, linked libraries, and undefined symbols are scanned
in CI. Its translation units may not include a path containing `opensubdiv`,
may not contain an `OpenSubdiv`, `Far`, `Bfr`, `Osd`, `Sdc`, or `Vtr` symbol,
may not link an OpenSubdiv library, and may not call an existing SLIMED row
provider. It constructs the Loop subdivision matrix directly from the published
stock Loop masks and the oriented one-ring. A second, separately coded uniform
subdivider shares only fixture parsing and scalar/vector containers with the
eigenanalysis implementation. The build emits the compiler dependency file and
the link map; a source/dependency scan plus `nm -u` and `otool -L` (or the Linux
equivalents) is a mandatory B2 check. Any forbidden dependency makes the oracle
uncovered rather than weakening this check.

**Dependency and CI ownership.** B2 owns exactly one dedicated workflow,
`.github/workflows/bfr_qualification.yml`, in addition to its proof code,
runner, tests, and evidence document. This narrow ownership is part of the B2
qualification claim: it is not permission to edit the `Makefile`, an existing
workflow, or a default build. The workflow runs on `macos-26`, checks out the
exact pull-request head, and provisions MPFR 4.2.2, its GMP dependency, and
OpenSubdiv 3.7.0 under the runner temporary directory from upstream release
archives whose versions, URLs, and SHA-256 checksums are literal workflow
inputs. It records the GMP version and archive hash as build provenance; MPFR
itself remains fixed scientifically and operationally at exactly 4.2.2. A
package-manager `latest`, an ambient Homebrew keg, or an unverified download is
forbidden.

The B2 runner accepts explicit `MPFR_ROOT` and `OPENSUBDIV_ROOT` values and may
not download dependencies or search ambient prefixes. It compiles the oracle
with `-I$MPFR_ROOT/include`, `-L$MPFR_ROOT/lib`, an rpath to that library
directory, and `-lmpfr -lgmp`; it separately locates the OpenSubdiv proof
libraries below `OPENSUBDIV_ROOT`. The compile-time/runtime version equality,
resolved-library containment below the declared roots, library hashes,
dependency file, link map, source scan, `nm -u`, and `otool -L` checks are all
performed by the runner. Its `--require-proof-dependencies` mode exits nonzero
for a missing root, version mismatch, library escaping either root, forbidden
symbol, or missing audit artifact; the dedicated workflow must use that mode
and is not allowed to report `skipped`. Local absence may be recorded as
pending evidence, but B2 cannot pass its gate until this exact-head workflow is
green. Thus dependency provisioning belongs to the workflow, dependency use
and auditing belong to the B2 runner, and neither responsibility leaks into the
production build.

**Arithmetic, eigendecomposition, and rigorous row enclosure.** All numeric
oracle operations use a repository-owned `MpfrInterval` containing two
independent `mpfr_t` endpoints, `lo` and `hi`, each initialized by
`mpfr_init2(...,544)` to an exact 544-bit significand (more than 160 decimal
digits). The implementation uses the MPFR C API from exactly MPFR 4.2.2; both
compile-time `MPFR_VERSION_STRING` and runtime `mpfr_get_version()` must equal
`4.2.2`, and the strings, resolved library path, and library SHA-256 are emitted
in the report. A version mismatch or unavailable MPFR is oracle-uncovered. The
scalar Boost MPFR wrapper is not an interval implementation and is forbidden on
the proof path.

Every primitive names its rounding direction explicitly. Addition uses
`mpfr_add(lo,a.lo,b.lo,MPFR_RNDD)` and
`mpfr_add(hi,a.hi,b.hi,MPFR_RNDU)`; subtraction pairs `a.lo-b.hi` downward and
`a.hi-b.lo` upward. Multiplication evaluates all four endpoint products into
544-bit temporaries, downward for the minimum and upward for the maximum.
Division first rejects a denominator interval containing zero, then forms its
reciprocal with `1/b.hi` downward and `1/b.lo` upward and uses interval
multiplication. Square root rejects a negative lower endpoint and calls
`mpfr_sqrt` downward on `lo` and upward on `hi`. Decimal fixture fields and
targets are parsed as exact decimal strings into downward/upward endpoints;
integers and rationals use exact MPFR setters.

The only transcendental required by the stock masks is `cos(2*pi/N)`. Its
argument interval is built from
`mpfr_const_pi(...,MPFR_RNDD/MPFR_RNDU)` and directed interval arithmetic. The
code must certify `0 <= angle.lo <= angle.hi <= pi.lo`, where cosine is
monotone decreasing, then call `mpfr_cos(angle.hi,MPFR_RNDD)` for the lower
endpoint and `mpfr_cos(angle.lo,MPFR_RNDU)` for the upper endpoint. Any other
cosine domain is rejected rather than passed to an unproved endpoint rule.
Matrix multiplication, dot products, norms, Gram-Schmidt, box-spline rows,
affine chain rules, edge lengths, and error bounds are composed term by term
only from these primitives; no nearest-rounded scalar, unchecked fused
operation, or process-global default rounding mode is a proof bound. The wrapper
clears MPFR status flags before each primitive; afterward, NaN, infinity,
invalid, divide-by-zero, overflow, underflow, and range flags fail closed. An
inexact flag is expected and does not weaken the directed enclosure. Any branch
whose ordering is not certified by disjoint endpoints is oracle-uncovered.

B2's audit scans source and symbols so proof code can call MPFR only through
this interval module, rejects `mpfr_float_backend` and any MPFR arithmetic call
without a literal `MPFR_RNDD` or `MPFR_RNDU`, checks the linked MPFR identity
above, and runs containment tests for every primitive and matrix operation.
Mutation tests replace one downward/upward mode at a time and must fail. This
audit is part of coverage, not advisory. Conversion to `double` occurs only at
the diagnostic midpoint-serialization step below, after the five depth
intervals have been intersected. The serialized value is
exactly reimported before `E_coeff` and `E_geom` are evaluated; neither it nor any other
nearest-rounded scalar may replace directed interval proof arithmetic.

The ambient coordinates are original source IDs in increasing numeric order,
with the Euclidean inner product. For a simple real eigenvalue, its eigenvector
has Euclidean norm one; among components of maximum absolute value, the
smallest source ID is the pivot, and its component is positive. For a repeated
real eigenvalue, the implementation first encloses its spectral projector,
then scans the ambient unit vectors in source-ID order, projects them, and
applies deterministic modified Gram-Schmidt. A projected vector is accepted
only when its interval lower bound on Euclidean residual norm exceeds
`1.0e-60`; it is then normalized and signed by the same smallest-source-ID
pivot rule. Blocks are ordered by decreasing real eigenvalue, then increasing
block dimension; vectors inside a block retain scan order. These rules, rather
than a library solver's arbitrary rotation, define `V`. The condition number is
exactly `kappa_infinity(V) = ||V||_infinity * ||V^-1||_infinity`.

Each valence is verified separately. Every eigenvalue must have an interval
imaginary part containing only zero; otherwise that valence is uncovered. For
every simple eigenpair or repeated real invariant block, the normalized
infinity residual
`||S*V - V*Lambda||_infinity /
max(1,||S||_infinity*||V||_infinity)` is at most `1.0e-70`; the assembled basis
and inverse satisfy both infinity-norm identity residuals at most `1.0e-70`;
the constant mode is one; the two-dimensional tangent block agrees with
`lambda = (3 + 2*cos(2*pi/N))/8` to `1.0e-70`; and
`kappa_infinity(V) <= 1.0e12`. Let `Q` be the two tangent columns produced by
the repeated-block procedure. The tangent comparison is the ambient,
source-ID-ordered Euclidean projector `P = Q*transpose(Q)`, not a comparison
of individual tangent vectors. Failure of any check marks that valence
uncovered. Any eigenvalue ordering, pivot maximum, or Gram-Schmidt acceptance
comparison not certified by the fixed interval endpoints also marks it
uncovered rather than invoking a solver-dependent tie break.

The mandatory primary computation is Stam eigenanalysis, not uniform
subdivision. For the ordered local control vector it constructs the published
stock-mask subdivision matrix `S`, certifies interval enclosures of `V`,
`Lambda`, and `V^-1` (including repeated invariant blocks), and computes the
depth power as `S^d = V*Lambda^d*V^-1`. A floating candidate decomposition is
only a seed: interval Krawczyk inclusion and the invariant-block residual and
separation checks must certify the enclosures before they can contribute to a
row. Failure is oracle-uncovered.

Every original control source enters that local vector as its basis row `e_i`.
For the sample's child sequence, the exact extraction matrix `R_path,d` selects
the regular controls after the eigenpower, so the depth-`d` Stam row is the
regular box-spline row times `R_path,d * V*Lambda^d*V^-1`. Powers of a repeated
block are matrix-block powers, never independently powered arbitrary vectors.
On a child boundary, test the closed child domains in the fixed order
`T0,T1,T2,Tc` and take the first match. Let `d0` be the first depth at which
the selected triangle has the complete regular 12-control box-spline support.
At each of the five depths `d = d0,d0+1,...,d0+4`, the primary Stam route
evaluates all six exact regular-patch source rows
`position,du,dv,duu,duv,dvv` and transforms them to the canonical coarse frame
with `B = A_d*Jk`. The maximum allowed depth is fixed: `d0+4 <= 30`.

For one row and source `i`, intersect its five outward-rounded coefficient
intervals to obtain `[lo_i,hi_i]`. Every intersection must be nonempty. The
diagnostic serialized coefficient `d_i` is the intersection midpoint rounded
once to finite binary64. It is then imported exactly into a fresh 544-bit MPFR
value with `mpfr_set_d(...,MPFR_RNDN)`, whose ternary return must be zero. This
is the required exact binary64 import of `d_i`; an approximate decimal reparse
is forbidden. Define

```text
epsilon_i = max(abs(d_i - lo_i), abs(hi_i - d_i))
E_coeff = sum_i epsilon_i
E_a = sum_i ([lo_i,hi_i] - d_i) * P_i[a]
E_geom = max_a(max(abs(lower(E_a)), abs(upper(E_a))) / lower(L_M)).
```

All subtractions, products, sums, absolute values, maxima, and endpoint reads in
these definitions use the directed interval primitives above. Fixture decimal
coordinate `P_i[a]` is its outward-rounded MPFR enclosure. `L_M` is an
outward-rounded enclosure of the exact maximum control-edge Euclidean length,
and its lower endpoint must be positive. Both `E_coeff` and `E_geom`, separately
for each of the six rows, must be at most one tenth of that row's D10 target.
Thus the bound includes binary64 midpoint serialization; an exact singleton
interval has zero width but has `epsilon_i=0` only when its value is exactly
representable by `d_i`. No ratio or division by a row difference is performed,
so a zero sequence cannot create `0/0`.

Candidate accuracy is decided directly against the certified interval, never
by adding an informal allowance to a midpoint difference. Each finite candidate
binary64 coefficient `c_i` is imported exactly into a fresh 544-bit MPFR value
with the same zero-ternary requirement. This is the
required exact binary64 import of `c_i`; an approximate decimal reparse is forbidden.
These exact binary64 imports and the final `mpfr_get_d(...,MPFR_RNDN)` serialization are the
only nearest-rounding operations permitted on the proof path; the audit still
requires directed rounding for every arithmetic primitive. On the sorted
source-ID union, with a missing candidate source represented by exact zero,
define

```text
u_i = max(abs(c_i - lo_i), abs(c_i - hi_i))
U_coeff = sum_i u_i
D_a = sum_i ([lo_i,hi_i] - c_i) * P_i[a]
U_geom = max_a(max(abs(lower(D_a)), abs(upper(D_a))) / lower(L_M)).
```

`U_coeff` is a rigorous upper bound on the coefficient `l1` error for every
oracle row inside the enclosure, and `U_geom` is the corresponding Cartesian
`l-infinity` upper bound. Both must satisfy that row order's D10 target at every
required sample. Pointwise midpoint differences are diagnostic only and may
not decide PASS. A nonfinite `d_i`, inexact `d_i` import, empty intersection,
missing regular support by depth 30, nonpositive `lower(L_M)`, or failed
`E_coeff`/`E_geom` serialization bound is oracle-uncovered. Once that oracle row
is covered, a nonfinite `c_i`, failed `c_i` import, or `U_coeff`/`U_geom` above
the D10 target is a candidate FAIL and may never be relabeled oracle-uncovered.

The mathematical justification is the Loop refinement identity: after the
complete regular support is reached, the exact Stam eigenpower followed by
exact box-spline evaluation represents the same six coarse-frame linear
functionals at every later depth. Thus the five primary interval rows enclose
one basis-invariant functional even though the mandatory algorithm computes it
through the canonical eigendecomposition. A position-mode eigenvalue heuristic
is never applied to derivative rows. Direct stock-mask propagation is the
separate cross-check below; it may neither replace the primary Stam rows nor
turn a failed eigendecomposition into coverage.

**Canonical face coordinates.** For every oriented base triangle
`(v0,v1,v2)`, the only public comparison frame is

```text
q = (u,v),  barycentric(q) = (1-u-v, u, v),
v0 = (0,0), v1 = (1,0), v2 = (0,1).
```

This is exactly OpenSubdiv 3.7.0 Bfr's triangle convention in
[`Bfr::Parameterization::GetVertexCoord`](https://github.com/PixarAnimationStudios/OpenSubdiv/blob/v3_7_0/opensubdiv/bfr/parameterization.cpp)
at tagged commit `9dab8a47bfbb1388ec8388fe61f5f916e6123f38`.
For Loop, a coarse triangle is regular, so
[`Far::PtexIndices`](https://github.com/PixarAnimationStudios/OpenSubdiv/blob/v3_7_0/opensubdiv/far/ptexIndices.cpp)
assigns one Ptex face and the upstream 3.7.0
[`bfr_evaluate` Far comparator](https://github.com/PixarAnimationStudios/OpenSubdiv/blob/v3_7_0/regression/bfr_evaluate/farPatchEvaluator.cpp)
passes the same pair unchanged to `PatchMap::FindPatch`. Therefore the frozen
coarse maps are `q_Bfr = q_Far = q`; no axis swap or reflection is permitted.
B2 must nevertheless prove the three corners, the center `(1/3,1/3)`, and the
three directed edge midpoints on a known regular face against the analytic
box-spline route before using an irregular comparison.

For Stam evaluation with extraordinary corner `vk`, the oriented local corner
triple is `(E,A,B) = (vk,v(k+1 mod 3),v(k+2 mod 3))`, and `x=(xi,eta)` stores
the barycentric weights of `(A,B)`. The complete affine maps `x = Jk*q + ck`
are

```text
k=0: J0 = [[ 1, 0],[ 0, 1]], c0 = [0,0]
k=1: J1 = [[ 0, 1],[-1,-1]], c1 = [0,1]
k=2: J2 = [[-1,-1],[ 1, 0]], c2 = [1,0].
```

They are orientation preserving (`det(Jk)=1`) and choose no new corner order.

**Sub-patch maps and derivative rescaling.** At each midpoint subdivision, a
parent triangle in coordinates `x` is mapped to child-local coordinates `y`
by exactly one of

```text
T0(x) = (2*xi,                 2*eta)
T1(x) = (2*xi - 1,             2*eta)
T2(x) = (2*xi,                 2*eta - 1)
Tc(x) = (2*xi + 2*eta - 1, 1 - 2*xi).
```

The selected child sequence is emitted for every sample. Composing it gives
`y = A_d*x + b_d`, and the complete map from canonical coordinates is
`y = B*q + b`, with `B = A_d*Jk`. If the exact regular box-spline patch returns
the column pair `G_y=[X_y0 X_y1]` and component Hessian `H_y`, the values to
compare are

```text
G_q = G_y * B
H_q = transpose(B) * H_y * B.
```

This supplies the first-order factor `2^d`, the second-order factor `4^d`, and
all rotations/reflections from center children without a scalar shortcut.
The eigenvalue powers transform control data only; they are not an additional
derivative factor.

Far's internal sub-patch affine map is frozen directly from OpenSubdiv 3.7.0
[`PatchParam::NormalizeTriangle`](https://github.com/PixarAnimationStudios/OpenSubdiv/blob/v3_7_0/opensubdiv/far/patchParam.h):
unrotated `y=2^d*q-(U,V)` and rotated
`y=(2^d-U,2^d-V)-2^d*q`. Its
[`EvaluatePatchBasis`](https://github.com/PixarAnimationStudios/OpenSubdiv/blob/v3_7_0/opensubdiv/far/patchBasis.cpp)
already applies the corresponding depth and rotation signs to first and second
rows. B2 consumes those returned rows in the coarse `q` frame and must not
rescale them a second time. It records `PatchParam` depth/rotation and verifies
both an unrotated and a rotated sub-patch against the analytic regular face.
Bfr `EvaluateStencil()` similarly returns derivatives in the face
`Parameterization` frame and receives no extra depth factor.

**Order norms and dimensions.** Source rows are aligned on the sorted union of
original source IDs, with a missing coefficient treated as zero. For derivative
order `r`, the primary error is the coefficient `l1` norm. The geometric
cross-check is the Cartesian `l-infinity` norm after applying the row difference
to fixture positions, divided by `L_M`, the maximum Euclidean length of any
control-mesh edge in that fixture. `L_M` is computed once from checked-in bytes
and must be finite and positive. Position has units `L`; first derivatives have
units `L / canonical-parameter`; second derivatives have units
`L / canonical-parameter^2`. Their row norms are respectively dimensionless,
per-parameter, and per-parameter-squared. Both the row norm and normalized
geometric cross-check must satisfy the order's D10 target through the rigorous
`U_coeff` and `U_geom` upper bounds above, not through a serialized midpoint
difference. Position-row sum one and derivative-row sum zero remain the
separate `1.0e-12` invariants; satisfying a sum rule cannot satisfy an accuracy
target.

**Extraordinary-vertex sampling.** In the Stam frame define the dimensionless
radius `r = xi + eta = 1 - barycentric(E)`. No accuracy comparison is claimed
for `r < 2^-8`. The fixed trend radii are `r = 2^-1, 2^-2, ..., 2^-8`, and each
radius uses the three fixed rays `(xi,eta) = r*(1/4,3/4)`,
`r*(1/2,1/2)`, and `r*(3/4,1/4)`. No value at `r=0` is requested. Results are
grouped by fixture, oriented face, extraordinary corner, valence, radius, ray,
and derivative order; no single-radius summary may replace the trend.

**Isolation and coverage.** A corner is isolated only when, after applying the
recorded midpoint child sequence, its evaluation patch contains exactly one
non-valence-6 vertex and every other vertex in the patch's required one-ring is
valence 6. B2 tests depths 0 through 12 and records the first isolating depth.
No isolation by depth 12, a failed eigenbasis check, a failed parametric-map
check, or a failed uniform cross-check marks that fixture/corner/valence
oracle-uncovered. Adjacent-extraordinary fixtures are never assumed covered at
depth zero. An uncovered item supplies no evidence for or against either
candidate.

**Independent uniform-subdivision cross-check.** The separately coded MPFR
interval uniform subdivider applies the stock even/odd Loop masks directly for
depths 0 through 30. It starts the complete coarse mesh from original-source
basis rows, recursively expands the exact backward mask-dependency closure for
the requested refined controls, and memoizes only that sparse closure; this is
algebraically identical to full uniform refinement without materializing
`4^d` faces. It uses its own stock-mask and refined-index code and may not call
the primary `S`, eigenvalue, eigenvector, matrix-power, or extraction
implementation. For every primary sample and each of its five depths, it
evaluates the same regular box-spline functional after direct propagation.
Every direct coefficient interval must overlap the corresponding primary Stam
interval source by source, and its independently intersected five-depth rows
must satisfy the same coefficient and normalized geometry uncertainty bounds.

Additionally, at every original extraordinary vertex it constructs the
published exact Loop vertex-limit position row directly; at the dyadic interior
vertices reached by `(1/4,1/4)`, `(1/2,1/4)`, and `(1/4,1/2)` it constructs the
five-depth position-row intersection. These position intervals must overlap the
primary position intervals source by source, and the resulting coefficient and
normalized geometry bounds must each be at most
`0.1 * irregular_position_row_accuracy`. The extraordinary tangent eigenspace
is compared as the source-ID-ordered Euclidean projection matrix defined
above; `||P_eigen-P_uniform||_infinity <= 1.0e-20` in interval arithmetic.
These checks validate the primary Stam oracle; they are not candidate accuracy
rows, and uniform success cannot supply coverage when the primary route fails.

### 3.3 Frozen D10 targets (approved 2026-08-08)

B2p fixes the following values before B2 exists. They are defensible a priori:
the position value inherits the already frozen regular-row gate, while the
first- and second-order values apply fixed factors of five per derivative order.
That order ratio is the pre-existing upstream OpenSubdiv regression policy
already recorded in section 3.1; B2p uses the repository's stricter existing
`5.0e-6` regular scale as its position anchor rather than importing an upstream
candidate observation. No Bfr or Far output from this repository contributes to
any value. The user explicitly approved D10 on 2026-08-08 after B2p froze these
scientific gates and before B2 began. The approval changes no value; any later
widening remains a blocker under **S5**. It also accepts the frozen coverage
challenge recorded in section 7: the
seeded hull has no coarse valence-6 vertex and contains valence-3 corners, so an
honest B2 run may leave items oracle-uncovered or may fail a target. Approval
does not predict success and does not authorize a later fixture or tolerance
change in response to those results.

| Name | Numeric value | Dimension and norm | A-priori rationale | Owning gate |
| --- | ---: | --- | --- | --- |
| `irregular_position_row_accuracy` | `5.0e-6` | Max over samples of source-union coefficient `l1` and geometry-normalized Cartesian `l-infinity`; position order. | Existing frozen regular-row scale. | D10 / B2 D9a irregular-oracle gate. |
| `irregular_first_derivative_row_accuracy` | `2.5e-5` | Same paired norms for each of `du`,`dv`; per canonical parameter. | One fixed upstream derivative-order factor of five. | D10 / B2 D9a irregular-oracle gate. |
| `irregular_second_derivative_row_accuracy` | `1.25e-4` | Same paired norms for each of `duu`,`duv`,`dvv`; per canonical parameter squared. | Two fixed upstream derivative-order factors of five. | D10 / B2 D9a irregular-oracle gate outside the inner radius. |
| `flip_pair_row_changed_linf` | `1.0e-12` | Absolute coefficient `l-infinity` over the source-ID union; missing source is zero. | Existing invariant scale, well above double roundoff; locality only, not accuracy. | B2 locality report, not D9a accuracy. |

A flip-pair face is `changed` when any entry in the hash-covered section 7
`locality_sample_manifest` and any of its six rows exceeds
`flip_pair_row_changed_linf`; otherwise it is reusable. Omitting, reordering, or
altering a manifest entry or row name is fixture drift. The value is fixed near
the existing row-sum invariant scale, far above double roundoff and far below
every accuracy target, without reference to a candidate run.

### 3.4 Pending D12 B2-readiness criteria and execution protocol

These criteria are frozen before a Bfr or Far executable exists in this lane.
They are deliberately loose **operational fail-stop budgets**, not evidence that
either candidate is fast and not a substitute for D8's later coordinate-only
production budget. No candidate output was used to choose them. D12 remains
pending technical review, independent scientific review, and explicit user
approval; until then B2 is stopped.

The reference platform is a dedicated Apple-silicon (`arm64`) macOS runner on
AC power, with no thermal-pressure indication and no other repository job
executing. macOS does not provide a supported general-purpose API for pinning
this process to performance cores, so no affinity claim is permitted. Record
macOS version, hardware model, chip, performance/efficiency core counts,
physical memory, compiler, optimization flags, OpenSubdiv identity, and clock
source in the evidence JSON. A run on Intel macOS, a virtualized or shared
runner, or a thermally pressured host is reported for information as
`UNQUALIFIED_PLATFORM` and cannot pass or fail these numeric gates. This
platform scoping prevents unexplained host variance from becoming a tolerance
change; changing it requires a reviewed D12 amendment before rerunning B2.

The preparation operation begins immediately before construction of a fresh
full-mesh `Far::TopologyRefiner`, then includes candidate construction of all
face surfaces and the six source-keyed rows at every manifest sample, and ends
only after the complete immutable row collection is validated. It excludes
fixture parsing, oracle work, JSON serialization, and disk I/O; each candidate
builds the same pinned refiner input inside its own measured operation. Each exact
`(candidate, fixture, approximation-level, applicable-cache-mode)` case runs in
a fresh process, performs **3 unrecorded warmups followed by 15 measured
preparations** in one process, discards no measured repeat, reports all 15
nanosecond durations, and gates on their ordinary median (the eighth sorted
value). System monotonic wall time is the unit. The fixed sweeps are Bfr
`approxLevelSmooth = 2,3,4,5,6,7,8` with `approxLevelSharp = 6`, and Far
isolation level `2,3,4,5,6,7,8`; equal integers are not treated as
commensurable settings. Bfr timing and RSS run separately with caching disabled
and with the serial `SurfaceFactoryCache`; Far has one proof-only uncached
construction mode, recorded as cache mode `not_applicable`, and is not run
twice under invented Bfr cache labels. Numeric timing/RSS use the recorded
non-sanitized Release proof build. The TSan build below is a separate
categorical threading profile and cannot supply a numeric cost or RSS PASS.

| Name | Frozen criterion | Rationale and failure semantics |
| --- | ---: | --- |
| `b2_preparation_median_ms` | `<= 1000.000` for every valid closed-fixture case at every fixed sweep level and each applicable mode defined above | A one-second preparation of at most 192 faces is an a-priori interactive proof-run safety ceiling, not an observed speed target. Any nonfinite/negative duration, missing repeat, or median above the ceiling is `FAIL`. |
| `b2_preparation_single_run_failstop_ms` | `<= 10000.000` for every measured repeat | Ten seconds catches hangs hidden by an otherwise passing median. Timeout, signal, allocation failure, or any repeat over the ceiling is `FAIL`; it is never discarded as an outlier. |
| `b2_retained_row_payload_bytes_per_face` | `<= 98304` bytes for every valid closed-fixture case | Exact logical retained payload after validation. For a face with `S` samples, `U` validated face-union source IDs, and `C` total coefficient entries across its exactly `6*S` sparse rows, the byte count is exactly `12 + 4*U + 72*S + 12*C`: signed 32-bit face ID; unsigned 32-bit sample and union counts; `U` signed 32-bit union IDs; three binary64 sample fields; and, per row, unsigned 32-bit kind/count plus one signed 32-bit source ID and one binary64 coefficient per entry. Allocator padding/capacity, refiner memory, executable text, and oracle memory are excluded and reported separately. A missing count, non-six-row sample, arithmetic overflow, or larger value is `FAIL`. The dense upper-bound illustration for 24 irregular trend samples and all 42 refined-icosahedron sources is 74,484 bytes, leaving 23,820 bytes below this a-priori 96-KiB fail-stop; no implementation may omit the row-repeated source IDs to improve the metric. |
| `b2_preparation_peak_rss_delta_mib` | `<= 64.000` MiB for every valid closed-fixture preparation process | On macOS, take the baseline `MACH_TASK_BASIC_INFO.resident_size` after fixture load but before refiner construction, then sample after refiner construction, factory/cache construction, every completed face-row insertion, and immutable-package publication; gate on the maximum observed nonnegative increase divided by `1048576`. A negative observation is clamped only for reporting to zero; a missing named boundary, sampling failure, process failure, or a larger delta is `FAIL`. The 64-MiB fail-stop is intentionally generous for this at-most-192-face corpus and does not assert production scalability or an unsampled continuous-time peak. |

The complete machine-readable execution order is
`data/fixtures/candidates/b2_readiness_v1/execution_manifest.json`. Its 17
ordered entries map, without omission, all 14 unified-plan section 8 rows and
all three section 7 additions to either an exact checked-in fixture or one exact
deterministic mutation. Coordinate perturbation adds binary64 deltas
`(+0x1p-8,-0x1p-9,+0x1p-10)` to vertex row 1 of the asymmetric bipyramid.
Winding reversal swaps columns 1 and 2 of torus face row 0. The open case
deletes torus face row 0. The duplicate/non-manifold case appends an exact copy
of torus face row 0. No B2 code may choose a replacement or silently create a
different case. The manifest preserves the B2p stable locality-sample manifest
and its shared-hull rule: `b2p_valence789` and
`b2p_single_flip_family/base` count once as mesh-level evidence.

Threading is categorical rather than a timing ratio. The matrix is
`cache_disabled` and `SurfaceFactoryCacheThreaded`, each at concurrent worker
counts `1,2,4`, with 20 complete preparation rounds per count and exact byte
identity of validated rows across workers and rounds. A support claim requires
zero ThreadSanitizer findings from a build in which **both the B2 proof and all
linked OpenSubdiv 3.7.0 translation units are TSan-instrumented**. An
uninstrumented OpenSubdiv build is `UNQUALIFIED`, never PASS. Any detected race
is `UNSUPPORTED/BLOCKING` for that mode. Cache-disabled concurrent preparation
and serial cached preparation are independently reported and qualified; a
threaded-cache result cannot confer status on either. Missing mode/count/round,
row mismatch, crash, or sanitizer finding is blocking. This adds no automatic
fallback and does not weaken the existing section 4 threading rule.

The numeric criteria apply only after D12 approval. Widening a number, changing
the aggregation or platform, omitting/reordering a manifest entry, or changing
a mutation after any candidate output is visible stops B2 under **S5**. D12
approval changes no D10 value or oracle input, does not decide D9a/D9b, and
does not authorize production or D8.

## 4. Bfr implementation facts to be pinned

Recorded so that reviewers can check the implementation against the library
rather than against an agent's summary. Every item must be re-verified against
the installed headers in B1 and pinned in B3.

1. `Bfr` was introduced in OpenSubdiv 3.5, so `>= 3.5` is the availability
   floor — but availability is not qualification. D1 approves stock **3.7.0**
   Loop semantics, and the ADR records that arbitrary ambient versions are not
   qualified. The check is therefore an **exact pin**,
   `OPENSUBDIV_VERSION_NUMBER == 30700`, matching the existing Valence-3
   provider, not a `>= 30500` floor. Valence 4 and 5 pin nothing today, which is
   a gap the generic backend must not inherit. Widening the pin later requires
   re-running the qualification evidence, not editing a comparison operator.
2. `bfr/surface.cpp` explicitly instantiates `template class Surface<double>;`,
   so double precision is available without a private build.
3. `Bfr::Surface<REAL>` provides three `EvaluateStencil` overloads: position;
   position plus `sDu`, `sDv`; and position plus `sDu`, `sDv`, `sDuu`, `sDuv`,
   `sDvv`. Weights are a linear combination of the **control** points and are
   sized by `GetNumControlPoints()`, not `GetNumPatchPoints()`.
4. `GetControlPointIndices()` returns original mesh vertex indices. This
   satisfies **A3**/**A4** directly and removes the `PatchMap` Ptex-identity
   check, `aggregate_row()`, and `exact_source_mapping()` machinery that each
   existing provider carries.
5. Exactly one mixed-derivative stencil is returned, matching **A5**.
6. `Bfr::SurfaceFactory::Options` defaults to `_approxLevelSmooth(2)` and
   `_approxLevelSharp(6)`. The existing providers use
   `Far::PatchTableFactory::Options patchOptions(5)`. The Bfr default is
   therefore *coarser* than current behaviour and must be set explicitly.
7. `SetApproxLevelSmooth(int)` assigns into an `unsigned char` with no
   clamping. SLIMED must validate the range and reject before use (**C1**);
   recording an unvalidated value in the topology key protects nothing.
8. Far's isolation level and Bfr's `approxLevelSmooth` are **not** the same
   quantity. Setting both to 5 is a confound, not a control. B2 sweeps both.
9. `Bfr::RefinerSurfaceFactory<CACHE_TYPE>` adapts a `Far::TopologyRefiner`
   with no custom adapter. Thread safety comes from
   `SurfaceFactoryCacheThreaded<MUTEX_TYPE, READ_LOCK, WRITE_LOCK>`. With
   caching disabled the factory is thread-safe but, per the documentation, far
   less efficient on irregular surfaces, which is SLIMED's entire case.
10. `SurfaceFactoryMeshAdapter` requires a *connected* mesh representation that
    can efficiently identify the incident faces of any vertex, ordered
    counter-clockwise for manifold vertices. SLIMED's per-vertex face order is
    currently derived from `nFaceX`/`nFaceY` grid arithmetic, so a custom
    adapter is **not** available until real connectivity ownership exists.
11. `FaceHasLimitSurface()` and `isFaceHole()` exist; initialization failure is
    expected for holes and some boundary interpolation options. That is a
    rejection path, not a fallback (**C2**).

### 4.1 Two-phase benefit attribution

The remeshing cost benefit and the API simplification benefit arrive in
different phases and must not be claimed together.

- **Phase 1 (B1-B4, `RefinerSurfaceFactory`)**: the mesh *is* a
  `Far::TopologyRefiner`, so a topology change still rebuilds the refiner.
  Claimable: API simplification, direct source IDs, one mixed row, whatever
  accuracy and cost result B2 measures. **Not** claimable: localized
  invalidation or a remeshing cost win.
- **Phase 2 (deferred, custom adapter)**: localized per-face invalidation
  becomes possible. Blocked on connectivity ownership, which is the same
  prerequisite as edge flipping itself, which is L7 in section 6. The adapter
  itself is L8 and is optional.

B2 quantifies the Phase-2 ceiling without implementing it, per B2 step 6.

## 5. Work packages

Lifecycle, review tiers, and command profiles are the unified plan's. Every
package is default-off, adds no production caller unless stated, and obeys
**C3**, **C5**, and **C7**.

### B0a - baseline inventory logic repair

Objective: make the V0 command profile pass at the authoritative base so that
every later package can produce clean evidence.

Tier: T1. Dependencies: none. Replaces nothing.

Allowed files, and nothing else:

- `scripts/inventory_unified_loop_baseline.py`
- `tests/test_unified_loop_baseline_inventory.py`
- `docs/adr_unified_loop_backend.md` and
  `docs/unified_irregular_loop_implementation_plan.md`, only where the two
  documents and the inventory disagree
- this plan

Forbidden: `src/**`, `include/**`, `Makefile`, `.github/**`, CUDA paths,
fixtures, tolerances, route flags, PR 176/182 source.

Steps:

1. Measure branch linearity from the **mainline fork point**
   (`git merge-base --fork-point` or an equivalent first-parent walk) rather
   than from a fixed `BASE_SHA..HEAD` range, so a completed package's own merge
   commit cannot violate the invariant.
2. Accept `TBD` as an explicit pending value for
   `generic_vs_cached_regular_median` and fail closed if any number, including
   the superseded `1.10`, is substituted without the named D8 measurement.
3. Add a mutation test proving that a future merge commit on main does not
   reintroduce the failure.

Evidence: `python3 scripts/inventory_unified_loop_baseline.py --check --json`
returns `"status": "ok"` at the exact PR head and at a synthetic
merge-commit-bearing descendant; focused mutation tests pass; `git diff --check`
clean; no forbidden-path diff.

Stop conditions: the guard can only be satisfied by deleting the linearity
invariant; or repairing it requires changing a frozen tolerance or fixture.

**PR 186 overlap.** PR 186 already implements step 1, and the uncommitted
working tree already implements step 2. Both touch the same two files. The
coordinator must present this choice to the user before writing code and may
not decide it:

- **(a)** merge PR 186 first on explicit instruction, then land steps 2-3 on
  top as B0a; or
- **(b)** supersede PR 186 with one combined B0a PR, then close PR 186 on
  explicit instruction.

Option (b) is recommended: one exact-head review of one coherent change. Either
way, PR 186 is not merged, closed, or retargeted without explicit user
instruction.

### B0b - inventory CI enforcement

Objective: make the repaired inventory a gate rather than a script nobody runs.

Tier: T1. Dependencies: **B0a merged and green.** Ordering is not cosmetic: a
workflow that enforces a still-broken invariant turns `main` red for every
contributor.

Rationale for the split: B0a changes Python invariant logic; B0b changes
repository automation, with its own review surface (trigger conditions, runner
image, Python version, workflow permissions, required-check configuration).
Bundling them would give one PR two primary claims, which **P1** forbids, and
would make a red CI indistinguishable from a wrong fix.

Allowed files, and nothing else:

- one workflow under `.github/workflows/`, either a new file or a minimal
  addition to the existing `ci.yml`
- this plan

Forbidden: `src/**`, `include/**`, `Makefile`, `scripts/**`, `tests/**`,
CUDA paths, fixtures, tolerances, route flags, and any change to
`cpp_maketest.yml` or `valence3_opensubdiv_proof.yml`.

Steps:

1. Run `python3 scripts/inventory_unified_loop_baseline.py --check --json` and
   the focused inventory test module on pull requests and on pushes to `main`.
2. Pin the runner image and Python version explicitly; the inventory must not
   silently change behaviour with an ambient interpreter upgrade.
3. Grant the job read-only repository permissions. It is a checker, not a
   writer.
4. Require no OpenSubdiv and no C++ build, so the job stays inside **C3**
   dependency isolation and cannot be blocked by an unrelated build failure.

Evidence: the workflow passes at the exact PR head; a deliberately mutated
policy anchor pushed to a scratch branch makes the job fail; the job does not
install OpenSubdiv; existing workflows are unchanged.

Stop conditions: enforcing the inventory requires relaxing an invariant to keep
CI green; or the job cannot run without a compiler or OpenSubdiv.

### B0c - record the D1 and D2 approvals

Objective: move D1 and D2 from proposed to approved in the decision record, with
the inventory's expected status strings updated in the same commit.

Tier: T1. Dependencies: B0a merged. May be scheduled before or after B0b; the
coordinator serializes shared-worktree writes either way (**P2**).

Why it is its own package: `scripts/inventory_unified_loop_baseline.py` asserts
the exact D0-D8 status phrases, so an ADR status change and an inventory
expectation change must land together or the inventory fails closed. Bundling
that with B0a's linearity repair would give one PR two primary claims (**P1**).

User decision of 2026-08-06, to be recorded verbatim in scope and limits:

- **D1 approved.** Stock OpenSubdiv 3.7.0 Loop semantics are the
  forward-looking CPU **proof** baseline. Completed rows are not modified to
  reproduce legacy masks. This does **not** select Far versus Bfr, does **not**
  change the production default, and does **not** approve arbitrary production
  inputs.
- **D2 approved.** The initial generic proof scope is complete, closed,
  consistently oriented, two-manifold triangular meshes. Boundaries, holes,
  ghosts, non-triangles, non-manifold incidence, and inconsistent orientation
  must fail before mutation. This does **not** decide D2b and does **not**
  authorize production activation.

Allowed files, and nothing else:

- `docs/adr_unified_loop_backend.md`, D1 and D2 ledger rows and the execution-gate
  list only
- `scripts/inventory_unified_loop_baseline.py`, expected status strings only
- `tests/test_unified_loop_baseline_inventory.py`
- this plan

Forbidden: `src/**`, `include/**`, `Makefile`, `.github/**`, any other decision
row, any tolerance, any fixture, route flags, CUDA.

Steps:

1. Update the D1 and D2 rows to an approved status that records the scope limits
   above verbatim, including the explicit non-approvals.
2. Update the inventory's expected status strings and add a mutation test proving
   that a status change unaccompanied by the recorded limits fails closed.
3. Leave D0, D2b, D3, D4, D5, D8 statuses untouched, and add a test asserting
   they are unchanged, so this package cannot silently advance another decision.

Evidence: inventory `--check --json` returns `"status": "ok"`; the mutation test
rejects a D1 or D2 status change that drops a scope limit; the diff touches no
other decision row.

Stop conditions: recording D1 or D2 requires changing a tolerance, fixture, or
another decision's status; or the approved scope cannot be stated without
implying D2b, D9a, or a production default.

### B1 - topology key and row contract amendment

Objective: make the backend-neutral contract able to express which API produced
a row set and at what approximation setting, before either API is implemented.

Tier: T1. Dependencies: **B0a, B0b, and B0c all merged**; D1 and D2 approved,
exactly as the unified plan's WP3.1 already requires. B0b and B0c may land in
either order after B0a; B1 waits for all three.

Relationship: this **replaces the unified plan's WP3.1 required-contract list**
with that list plus the additions below. Every WP3.1 test requirement and stop
condition stays in force.

Additions to the **production** `LoopTopologyKey`:

- `evaluatorApi`: retained for diagnostics and cache identity, but **production
  construction must reject any value other than `bfr-surface`**, before any
  mutation (**C1**). A prepared package is never served to a request carrying a
  different value.
- `bfrApproxLevelSmooth` and `bfrApproxLevelSharp`: validated integers,
  range-checked before use because the library setter assigns into an
  `unsigned char` without clamping.
- `bfrCacheMode`: which `SurfaceFactoryCache` configuration produced the rows,
  since threaded and serial caching are qualified separately.
- `opensubdivVersion`: already required by **A6**. B1 treats this as **plain
  data**: an integer field carried in the key, with an unpopulated or zero
  value rejected before use (**C1**).

**No Far settings enter the production key.** `farIsolationLevel` and every other
Far configuration live only in B2's proof-only configuration under
`experiments/`. An earlier draft placed `far-limit-stencils` and
`farIsolationLevel` in the production key, which preserved a latent Far
production route reachable by configuration rather than by decision. That is
withdrawn. Correspondingly:

- **no production code may construct `Far::PatchTable`, `Far::PatchMap`, or
  `Far::LimitStencilTableFactory`**, and a test must prove it;
- `Far::TopologyRefiner` **is** permitted in production as the base-mesh adapter
  for `Bfr::RefinerSurfaceFactory`. That is the officially provided bridge and
  Bfr still owns surface construction and evaluation, so it does not make this a
  Far evaluator lane;
- adopting Far later requires a new explicit architecture decision and its own
  package, never a configuration change.

**B1 contains no OpenSubdiv include, type, or `static_assert`.** An earlier
draft of this plan asked B1 for a compile-time version-floor assertion, which
directly contradicts **A3** and WP3.1's own test that public headers contain no
OpenSubdiv include: a `static_assert` on `OPENSUBDIV_VERSION_NUMBER` requires
including `opensubdiv/version.h`. The version floor is a **backend**
responsibility and is owned in two places, both of which already link
OpenSubdiv:

- B2 carries a proof-local floor check inside its `experiments/` code;
- B3 carries the production floor assertion inside the backend translation
  unit, as B3 step 5 already states.

B1's only obligation is that the contract can *represent and validate* a
version, not that it can check one.

Tests: a prepared package with a different `evaluatorApi` or approximation
level must miss the cache; an out-of-range approximation level must be rejected
before any mutation (**C1**); an unpopulated version field must be rejected;
public headers still contain no OpenSubdiv type or include, proven by the
existing WP3.1 compile-time test.

### B2p - B2 preflight: freeze targets, fixtures, and oracle contract

Objective: create every input B2 must not be free to choose after seeing
results. B2p produces no comparison result and reaches no conclusion.

Tier: **T2**. Freezing a scientific target and hashing new fixtures is a
baseline-affecting act even though no measurement is taken.

Dependencies: **B0a, B0b, B0c, and B1 all merged**; D1 and D2 approved. B1 comes
first because B2p's fixture and target work is written against B1's contract.

Rationale for existing at all: B2's allowlist deliberately excludes this plan
and the ADR, so B2 cannot record its own frozen targets or fixture hashes
without editing files it does not own. An earlier draft required B2 to do
exactly that, which was unexecutable. Splitting the freeze into its own
package also makes **S5** compliance provable from commit order rather than
from an author's assurance.

Allowed files, and nothing else:

- this plan, sections 3.2 and 7, the tolerance additions, and the narrow B2
  dependency/CI ownership needed to execute section 3.2
- `docs/adr_unified_loop_backend.md`, tolerance ledger and fixture-hash table
- `data/fixtures/candidates/**`, new fixtures only
- `scripts/`, one fixture generator and the inventory expectation update
- `tests/`, focused fixture and inventory tests

Forbidden: `src/**`, `include/**`, `experiments/**`, any existing tolerance
value, any existing fixture byte, CUDA, route flags, PR 176/182 source.

Steps:

1. Declare the D10 irregular target names, values, rationale, and owning gate.
   Add them to this plan and to the ADR tolerance ledger in the same commit.
2. Write the complete section 3.2 oracle contract as a specification: the
   independence check, precision, convergence criterion, parametric remapping
   and per-order Jacobian rescaling, norms, inner radius, radius sequence, and
   coverage-reporting rules.
3. Generate the section 7 fixtures — the single-flip pair family, the valence
   7/8/9 mesh, and the adjacent-extraordinary mesh — each with a
   `candidate_metadata.json` recording generator, parameters, and closure and
   orientation validation.
4. Add SHA-256 hashes for every new fixture file to the ADR fixture table and
   extend the inventory to check them, so a later silent fixture edit fails
   closed.
5. Define **stable face correspondence** between the members of each flip pair:
   which faces are the same face, which are the two rewritten faces, and the
   identity rule used. Without this, the B2 locality metric is not computable.
6. Define the numeric row-comparison tolerance used to decide whether a face's
   rows "changed" between pair members, separately from the accuracy targets.

Evidence: the inventory passes and rejects a mutated or missing new fixture
hash; each fixture's closure, orientation, and manifoldness are validated by
test; no measurement or comparison result appears anywhere in the diff.

Gate: technical PASS; scientific PASS confirming the targets are defensible
*a priori* and the oracle contract is complete enough to be implemented by
someone who did not write it; explicit user D10 approval.

Stop conditions: a target can only be stated by reference to a measurement that
does not exist yet; the oracle contract cannot specify the derivative rescaling;
or a fixture's orientation or closure is ambiguous.

Suggested branch: `codex/bfr-far-preflight-targets`.

### B2 - Bfr qualification proof, with Far as regression comparator

Objective: produce the evidence for **D9a**, the Bfr qualification gate. B2
decides whether Bfr is adequate, not whether Bfr beats Far and not whether Bfr is
activated in production. Far runs only as a regression comparator. Proof only:
no production caller, no default change, no route.

Tier: **T2** (separate implementer, verification agent, technical reviewer,
scientific reviewer, gatekeeper). Qualifying an irregular surface representation
is baseline-affecting and cannot be reviewed as mechanical work.

Dependencies: B0a, B0b, B0c, B1, **and B2p all merged**, plus explicit user D10
approval of B2p's frozen targets, and the separate B2-readiness preflight merged
with explicit user **D12** approval. B2 cannot start on unfrozen inputs; that is
the whole point of B2p and D12 existing. Volume semantics are excluded, so
D3/D4 are not required.

Allowed files, and nothing else:

- new proof code under `experiments/`
- one new runner under `scripts/`
- focused tests
- `docs/bfr_qualification_evidence.md`
- one new dedicated workflow, `.github/workflows/bfr_qualification.yml`, only
  for checksum-pinned proof dependencies and the exact-head B2 audit

Forbidden: production geometry, energy, or force code; existing expected values;
route flags; CUDA; changes to any existing frozen tolerance; **and any write to
`data/fixtures/**`, to B2p's D10 targets, to the oracle contract, to fixture
metadata, or to fixture hashes.** B2 has read-only access to every B2p output.
Creating a new fixture inside B2 would defeat the freeze that makes **S5**
compliance provable from commit order. The `Makefile`, every existing workflow,
and every other `.github/**` path remain forbidden; the dedicated workflow may
not alter or become a dependency of default builds.

Steps:

1. Build Bfr and the Far comparator from the **same** full base-mesh
   `Far::TopologyRefiner`, so topology construction is not a confound. Use
   `Bfr::RefinerSurfaceFactory`; do not write a custom mesh adapter.
2. Consume the D10 targets, oracle contract, fixtures, face correspondence, and
   row-comparison tolerance **as frozen by B2p**. B2 may not restate, reinterpret,
   or adjust any of them; this plan and the ADR are outside B2's allowlist
   precisely so that it cannot. If a frozen input turns out to be wrong, stop and
   return it to B2p for a reviewed amendment rather than working around it.
3. Regular gate: for canonical `6/6/6` faces, evaluate each candidate against
   `SlimedLoopLimitSurfaceEvaluator` within the existing frozen
   `regular_row_and_route_parity = 5.0e-6` on position, first, pure second, and
   mixed second rows, and on the area and legacy-volume integrands. The analytic
   regular evaluator is the exact box-spline, so it is a genuine oracle for this
   case and the tolerance is not negotiable. The two failures are **not
   symmetric**:
   - **Bfr fails** -> blocking for the lane.
   - **Far fails** -> Far is disqualified as a regression comparator, and the
     failure is itself a severity-1 finding about the existing prototypes that
     must be reported and escalated. It does **not** veto a Bfr result that
     passes on its own, because Bfr's qualification is measured against the
     analytic evaluator and the Stam oracle, not against Far.
   An earlier draft made failure of *either* candidate blocking, which would have
   let a defect in the legacy implementation block migration away from it.
4. Irregular oracle: implement the section 3.2 Stam eigenanalysis oracle,
   validated at vertices against uniform-subdivision limit masks. Report each
   candidate's error against that oracle **as a trend over a declared sequence
   of radii approaching the extraordinary vertex**, never as a single pointwise
   value at the vertex. Declare the inner radius below which no comparison is
   claimed, and state per fixture whether the oracle achieved isolation and
   which valences have a verified eigenbasis. Do not compare the candidates to
   each other as if one were truth.
4a. Internal refinement convergence: for each candidate independently, raise
   only its own approximation setting and show that its rows converge. This
   needs no external oracle. A candidate whose rows do not stabilise is
   disqualified regardless of how it compares to the other.
5. Approximation sweep: sweep Far isolation level and Bfr
   `approxLevelSmooth` independently and publish error-versus-cost curves.
   State explicitly that the two knobs are not commensurable, so "both set to
   5" is a confound rather than a control.
6. Cost and locality: measure preparation wall time, row memory, and
   concurrent-preparation behaviour for both. For each flip-pair fixture, using
   B2p's stable face correspondence and row-comparison tolerance, report **two
   distinct quantities**:
   - `changed_faces`: faces whose rows differ between the pair members. This is
     the set that must be **recomputed** after a flip.
   - `reusable_faces = comparable_faces - changed_faces`: the maximum set a
     Phase-2 custom adapter could **reuse**.
   The saving is `reusable_faces`, not `changed_faces`. An earlier draft of this
   plan inverted this. Report both as a projection for Phase 2, never as a
   delivered benefit, and state `comparable_faces` explicitly so the ratio is
   reconstructible.
   Every preparation-cost and memory PASS/FAIL uses section 3.4 verbatim;
   candidate output cannot revise its platform, sweep, aggregation, ceiling,
   or failure semantics. D8's later coordinate-only production budget remains
   distinct and undecided.
7. Threading: run Bfr with caching disabled and with
   `SurfaceFactoryCacheThreaded`. Threaded caching may be claimed as supported
   **only** with a ThreadSanitizer-instrumented OpenSubdiv build; a TSan run
   against an uninstrumented library covers SLIMED's translation units only and
   must not be reported as library coverage. If a race is detected in the
   library cache, threaded caching is recorded as **unsupported and blocking**
   for that configuration, and serial preparation becomes the only qualified
   mode. A detected race is not downgraded to a performance trade-off. If no
   instrumented build is available, report threaded caching as **unqualified**,
   not as passing.
8. Emit complete JSON with independent schema validation and mutation tests for
   missing rows, nonfinite coefficients, dropped derivative order, swapped
   candidate labels, and accidental success.

Fixtures: every row of the unified plan's section 8 matrix, **plus** the new
rows in section 7 below, in the exact order and mapping frozen by section 3.4's
hash-covered execution manifest. The flip-pair family is mandatory, not
optional. B2 may materialize only the exact declared mutations in a temporary
directory and may not retain or substitute a fixture.

Gate:

- D10 targets were frozen before results, evidenced by commit order;
- D12 engineering criteria, execution manifest, and complete fixture corpus
  were approved and frozen before results, evidenced by commit order;
- `.github/workflows/bfr_qualification.yml` is green at the exact reviewed B2
  head in `--require-proof-dependencies` mode and publishes the dependency
  identities plus the complete independence audit;
- the report states Bfr PASS or FAIL against every D9a criterion, naming the
  specific failing criterion on FAIL, publishes Far's comparator results
  alongside, and explicitly declines to rank Bfr against Far on near-vertex
  accuracy;
- scientific reviewer confirms oracle independence, oracle validation against
  the vertex cross-check, and that no candidate was advantaged by an unmatched
  approximation setting;
- technical reviewer reproduces every fixture from a clean state.

Stop conditions:

- a D10 target is widened, reordered, or selectively omitted after results;
- exact MPFR 4.2.2 cannot be provisioned by the owned workflow, the proof only
  runs against an ambient dependency, or the independence audit is local-only;
- the report claims a remeshing benefit for Phase 1;
- the report claims a near-vertex accuracy ranking, or claims D9b;
- an oracle-uncovered fixture is counted as evidence for a candidate.

### B2 outcomes

Exactly one of these is the deliverable. Both are valid results under **P9**.

1. **Bfr qualified.** Bfr passes the regular `5.0e-6` gate, the `1.0e-12` row
   invariants, source-ID reconstruction, internal refinement convergence, the
   frozen D10 irregular targets, and the cost, memory, and threading budgets.
   D9a passes and B3 implements Bfr. Far remains a regression comparator.
   Production activation stays deferred to D9b after WP5.2.
2. **Bfr not qualified.** The specific failing criterion is named and published.
   This **blocks the lane**. It does **not** promote Far. Escalate to a new
   explicit architecture decision whose options include the unified plan's WP5.1
   patch-domain candidate, a different representation, or a separately gated
   package to harden Far. No agent may select any of those by inference, and no
   configuration change may route production to Far.

Far's own measured results are published either way, as comparator evidence. If
Far fails the regular gate that is a severity-1 finding about the existing
prototypes and is escalated on its own, but it neither qualifies nor
disqualifies Bfr.

In both outcomes, the measured near-vertex Far-Bfr disagreement magnitude is a
required deliverable in its own right, reported strictly as **observed
inter-method spread**.

It is **not** a floor on achievable irregular row accuracy, and must never be
described as one. Far and Bfr share an approximation *strategy* — local
subdivision plus a Gregory-style end cap — so their errors are expected to be
correlated. Correlated errors make the spread small while both methods are
inaccurate, so agreement is weak evidence of accuracy and the spread bounds
neither method's error. Any WP5.1 accuracy limit must be derived from converged
independent-oracle error, or left unresolved. An earlier draft of this plan
asserted the invalid floor interpretation; it is withdrawn.

Suggested branch: `codex/bfr-qualification-proof`.

### B3 - Bfr full-mesh provider

Objective: implement the generic interface for proof-only full-mesh topology
using `bfr-surface`. There is no API branch: Bfr is the only production
evaluator this plan authorizes.

Tier: **T2.** B3 creates the row source for the generic irregular backend, which
is baseline-affecting under the unified plan's tier rules. T1 is available only
if a separately reviewed classification establishes that the diff is purely
mechanical relative to an already-merged provider.

Dependencies: B1 and B2 merged; explicit user D9a pass and D10 approval; D1 and
D2 approved. The closed proof may proceed while D2b is pending, with the same
scope restriction the unified plan's WP3.2 states.

B3 must not describe Bfr as scientifically preferred over Far. D9a establishes
that Bfr is *adequate*; the production-target decision was a scope choice, and
production *activation* remains D9b after WP5.2. B3's PR body states both.

Relationship: this **replaces the unified plan's WP3.2 steps 1-3** with the
sequence below. WP3.2 steps 4-9, its evidence list, and all of its stop
conditions remain in force verbatim, including the `5.0e-6` regular equivalence
stop condition and the D2b requirement.

Steps:

1. One `Far::TopologyRefiner` from complete oriented triangle connectivity with
   explicitly reviewed Loop and boundary options, then one
   `Bfr::RefinerSurfaceFactory` over it.
2. Per physical face, `InitVertexSurface()`, then `GetControlPointIndices()`
   for the per-face union source list, then `EvaluateStencil()` at each
   approved sample for all six rows.
3. Reject rather than fall back when `FaceHasLimitSurface()` is false or
   initialization fails (**C2**).
4. Pin and emit the OpenSubdiv version, `approxLevelSmooth`,
   `approxLevelSharp`, cache mode, and every scheme option into the topology
   key and diagnostics.
5. Add the exact-version compile-time pin
   `OPENSUBDIV_VERSION_NUMBER == 30700` inside the backend translation unit.
   This is the only place in the B lane that includes an OpenSubdiv header for
   version purposes; B1 carries the version as data only.

Production seam tests, all mandatory:

- no production translation unit constructs `Far::PatchTable`, `Far::PatchMap`,
  or `Far::LimitStencilTableFactory`;
- production key construction rejects any `evaluatorApi` other than
  `bfr-surface` before mutation;
- an out-of-range `bfrApproxLevelSmooth` or `bfrApproxLevelSharp` is rejected
  before mutation.

Build gate: one new flag `USE_OPENSUBDIV_LOOP`. B3 adds **no** new runtime
selector; production selection remains the unified plan's single
`SLIMED_SUBDIVISION_BACKEND` in WP6.2. The repository must not grow a fourth
per-valence route (**A1**, **A9**).

### B4 - topology epoch cache and invalidation

Objective: unchanged from the unified plan's WP3.3.

Relationship: WP3.3 applies verbatim with three additions.

1. The cache key is B1's extended `LoopTopologyKey`. A changed `evaluatorApi`
   or approximation level must miss.
2. Where Bfr runs with `SurfaceFactoryCacheThreaded`, WP3.3
   step 5's race-focused harness covers the library cache as well as SLIMED's,
   and the serial-preparation fallback is exercised.
3. WP3.3 step 7 additionally reports the flip-pair re-preparation cost measured
   in B2 step 6, so the D8 discussion has a number for topology-change cost
   rather than only coordinate-only cost.

Note: the unified plan's D8 bounds coordinate-only evaluation and reports
preparation separately, with exactly one preparation per epoch. That is correct
for static topology. Under remeshing an epoch occurs per remesh step, and no
approved ceiling exists for re-preparation. B4 produces the measurement; the
ceiling itself is a later explicit user decision.

### B5 and later

The unified plan's WP4.1, WP4.2, WP5.1, WP5.2, WP6.1, WP6.2, WP6.3, WP7, WP8,
and WP9 apply unchanged, with two substitutions:

- read "WP3.1" as "WP3.1 as amended by B1";
- read "WP3.2/WP3.3" as "B3/B4".

WP4.1 and WP4.2 are deliberately backend-agnostic and require no Bfr-specific
change: they consume source-keyed rows, not OpenSubdiv objects.

Two unified-plan additions are required and are recorded here rather than
duplicated:

- **WP5.1 step 2** must include the section 7 fixtures below. The reassessment
  required testing "valences beyond 3/4/5 and randomized legal edge-flip
  topologies"; that requirement was lost when the reassessment was compressed
  into WP5.1 and is restored here.
- **WP5.1** must separate the two contributions to any post-flip energy change:
  the limit surface changed, and, for a graded quadrature candidate, the sample
  plan changed with valence. Conflating them makes the WP9 energy-discontinuity
  policy unverifiable.

## 6. Legacy disposition

The existing implementation is not one thing. Each stratum has a different
evidential value and therefore a different disposition. The governing principle
is that **no package in this plan modifies strata L1-L3 except to freeze or
label them.** The new route is built alongside; retirement is a separate PR
sequence after acceptance (**C7**, unified plan WP7).

### L1 - pre-OpenSubdiv legacy subdivision matrix

Artifacts: [`Mesh_setup_geometry.cpp:279`](../src/mesh/Mesh_setup_geometry.cpp:279)
`set_one_ring_vertices_sorted()`, and `get_subdivision_matrices()` in
[`Gauss_quadrature.cpp`](../src/mesh/Gauss_quadrature.cpp).

Facts: the predicate admits only all-`6/6/6` and all-`5/5/5` corner valences
and leaves `oneRingVertices` empty otherwise; the matrix it feeds describes one
valence-5 and two valence-6 corners; `d4`, `d7`, and `d8` are declared before
the branch that assigns them and remain uninitialized when no corner has
exactly five adjacent faces.

Disposition: **repair unconditionally, never extend.** The unified plan's
WP1.1a is the correct package and is unchanged by this plan; it may proceed in
parallel with B0a-B2 because file ownership is disjoint. Quarantine waits for
D5 (WP1.1b). This stratum is the oldest and least safe layer in the repository
and is the one place where work should start before D9a is decided.

### L2 - regular OpenSubdiv evaluator and row cache

Artifacts: [`OpenSubdiv_regular_evaluator.cpp`](../src/mesh/OpenSubdiv_regular_evaluator.cpp)
(1334 lines), [`Regular_limit_surface_row_cache.hpp`](../include/mesh/Regular_limit_surface_row_cache.hpp),
flag `USE_OPENSUBDIV_REGULAR`, selector `SLIMED_USE_OPENSUBDIV_REGULAR`.

Disposition: **keep, freeze, retire last.** This is load-bearing evidence, not
legacy debt. It is the exact analytic box-spline for regular faces, so it is a
genuine **oracle for that case**, and it anchors B2 step 3 and B3's `5.0e-6` stop
condition, and the performance baseline for D8's cached-route comparison. It
must not be modified, refactored, or renamed by any package here. Retiring it
before the generic route is accepted would destroy the only independent
regular-face check the programme has.

### L3 - exact per-valence production routes

Artifacts: [`Valence4_face_loop_route_preflight.cpp`](../src/energy_force/Valence4_face_loop_route_preflight.cpp)
(1880 lines), [`Valence5_opensubdiv_face_loop.cpp`](../src/energy_force/Valence5_opensubdiv_face_loop.cpp)
(725), [`Valence4_topology_source_mapping.cpp`](../src/mesh/Valence4_topology_source_mapping.cpp),
`OpenSubdiv_valence{3,4,5}_row_provider.cpp` (382/375/405), flags
`USE_OPENSUBDIV_VALENCE3` and `USE_OPENSUBDIV_VALENCE5`, selectors
`SLIMED_USE_OPENSUBDIV_VALENCE4`, `SLIMED_USE_OPENSUBDIV_VALENCE5`, and
`SLIMED_USE_OPENSUBDIV_VALENCE5_PHASE2`.

Disposition: **freeze as fixture-bound regression comparators; do not port to the
Bfr; retire through WP7 only after the generic route is accepted.**
D11 records this. Concretely:

- no package here adds a valence, generalizes a guard, or ports one of these
  providers to Bfr;
- the octahedron and icosahedron routes remain regression cross-checks for those
  fixtures in B2 and B3. They are comparators, not oracles: they share
  OpenSubdiv machinery and approximation strategy with the candidates, so
  agreement with them is not evidence of accuracy. Only the Stam evaluator
  (irregular) and the analytic box-spline route (regular) are oracles;
- the accepted narrow Valence-5 scientific result stays scoped to its fixture
  and never becomes evidence for the generic backend;
- deletion is mechanical, staged, and separate from activation, per WP7.

### L4 - unmerged Valence-3 stack

Artifacts: PR 176 root `46c06080`, PR 182 leaf `9587e3dc`, PR 185 fixture
archive `6fe58e86`.

Disposition: **finish the extraction already in flight, then supersede.** PR
185 implements the unified plan's WP0.2 option 1 by archiving the symmetric and
asymmetric bipyramid fixtures plus an archival note. Recommended sequence,
each step on explicit user instruction only:

1. review and merge PR 185, which preserves the scientifically useful evidence;
2. confirm the archived fixtures reproduce PR 182's recorded negative
   convergence result from `main` alone;
3. close PR 176 and PR 182 as superseded, recording their SHAs in the archival
   note so the negative result stays citable.

No agent closes, retargets, or merges either PR. PR 182 cannot reach `main`
independently of PR 176. The Valence-3 provider is not the target architecture
and its full-divergence volume must not be adopted implicitly by merging the
stack; that is D3's decision.

### L5 - assets to carry forward

These are not legacy debt and must be reused rather than reimplemented:

- [`Source_keyed_kernel_call.cpp`](../src/energy_force/Source_keyed_kernel_call.cpp):
  variable-cardinality source IDs with range, uniqueness, cardinality, and
  finiteness checks. Its seven-row compatibility sample stays the only place a
  mixed row is duplicated (**A5**).
- [`Adaptive_edge_flip_quality.hpp`](../include/mesh/Adaptive_edge_flip_quality.hpp):
  a clean, side-effect-free hinge predicate. Reused unchanged by WP9; it is the
  one piece of the flipping lane that already exists.
- the fixture corpus and its SHA-256 ledger in the ADR;
- the adversarial test patterns: fail-before-mutation, atomic rollback,
  serial/OpenMP envelopes, and JSON mutation testing.

### L6 - CUDA

Artifacts: `src/cuda`, `include/cuda`, PR 175 `3328068b`.

Disposition: **frozen** under D7 and **C5**. No package here touches CUDA.
B2 and B3 may read CUDA's x-only volume anchors for compatibility
characterization only. Whether CUDA can consume Bfr's rows is the
unified plan's WP8 question and is not prejudged by D9.

### L7 - required prerequisite: topology ownership and rebuild transaction

**Mandatory, and it must precede WP9 rather than follow its gate.** An earlier
draft of this plan merged this with the optional Bfr adapter below and sequenced
both after WP9's feasibility gate. That was wrong in two ways: WP9's own gate
already presumes transactional mutation, exact rollback, epoch increments, and
label and state preservation, so it cannot be *satisfied* without this work; and
making a mandatory prerequisite inseparable from an optional optimisation left
the prerequisite unowned.

Current state: SLIMED has no edge or halfedge ownership
([`Mesh.hpp:135`](../include/mesh/Mesh.hpp:135) is commented out),
`set_adjacent_faces_of_vertices_sorted()` derives per-vertex face order from
`nFaceX`/`nFaceY` grid arithmetic rather than connectivity, and
`set_one_ring_vertices_sorted()` recognises only all-`6/6/6` and all-`5/5/5`
corner valences.

Required content, drawn from Gate B and Gate E of
[`adaptive_edge_flipping_feasibility_2026-08-03.md`](../analysis/adaptive_edge_flipping_feasibility_2026-08-03.md),
which the unified plan's WP9 compressed away:

1. unique undirected-edge ownership keyed by `(min(u,v), max(u,v))` with its two
   incident faces, or an active halfedge representation if flips will be
   frequent;
2. one connectivity-derived adjacency and orientation rebuild that does not
   consult grid indices, validating a connected orientable two-manifold before
   commit;
3. a monotonically increasing `topologyGeneration` keying all derived topology
   state, which is the concrete mechanism **A6** and **A8** already require;
4. atomic stage, validate, commit, rollback, with exact restoration on
   rejection;
5. topology-aware checkpoint and restart: `SLIMED_RESTART_V2`
   ([`output.cpp:225`](../src/io/output.cpp:225)) stores no connectivity, so a
   run containing flips would restart on the input mesh's topology while loading
   observables computed on a different one;
6. periodic image pairing, since flipping one image of a periodic edge
   desynchronises the band, and insertion, material, layer, ghost, and boundary
   label transfer policy;
7. optimizer and dynamics consequences: NCG reset and line-search history
   invalidation, and rebuild of `DynamicMesh::mesh2surface` /
   `surface2mesh`, which hardcode the valence-6 weight
   ([`Dynamic_mesh.cpp:93`](../src/dynamics/Dynamic_mesh.cpp:93)) and are built
   through a dense inverse.

Sequencing: L7 is a prerequisite of WP9 and is independent of D9a, D9b, and
every B package. It may be scheduled in parallel with the B lane because its
file ownership is disjoint, and it must not be scheduled *after* WP9's gate.
It is not authorized by this plan; it needs its own package, reviewers, and
explicit user instruction.

### L8 - optional, later: custom Bfr mesh adapter

Optional and strictly downstream of L7. A `SurfaceFactoryMeshAdapter` over
`Mesh` requires a connected representation that can efficiently identify the
incident faces of any vertex, counter-clockwise ordered for manifold vertices —
which is exactly what L7 delivers. L8 is the only route to the Phase-2 localized
invalidation quantified by B2 step 6.

L8 is an optimisation, not a prerequisite for anything. If it is never
implemented, the B lane still works and WP9 is still reachable through L7. Do
not make L7 wait for L8.

## 7. Fixture additions

These rows are added to the unified plan's section 8 matrix and are mandatory
for B2, B3, and WP5.1. They exist because every current fixture stops at
valence 6, so no existing evidence covers what remeshing produces.

| Fixture/class | Topology purpose | Required checks |
| --- | --- | --- |
| Single-flip pair family: one closed triangulation plus N variants each differing by exactly one legal edge flip | Post-remeshing topology without needing mutation code; row locality measurement | Rows, source coverage, error versus oracle, changed-face count between pair members |
| Closed mesh containing valence 7, 8, and 9 corners | Coverage above valence 6, which no current fixture reaches | Rows, derivative sum rules, error versus oracle, force conjugacy |
| Adjacent extraordinary corners sharing an edge | Interacting irregular regions, not isolated ones | Rows, oracle error, quadrature sensitivity |

The flip-pair family is generated offline as static fixtures with documented
provenance and hashes. It requires no `Mesh` mutation, no edge ownership, and
no WP9 dependency, which is precisely why it can run now.

B2p freezes the concrete corpus as follows. The single-flip base is the
oriented 13-vertex/22-face convex hull produced by Python
`random.Random(14631)`: draw 13 triples `(a,b,c)` with
`a,b=randint(-12,12)`, `c=randint(1,12)`, map `x=a/c,y=b/c` to the unit sphere
by `(2x,2y,x^2+y^2-1)/(x^2+y^2+1)`, and enumerate the strict hull with exact
`Fraction` side tests. The accepted triples and every strict-side count are in
the hash-covered metadata. This is an a-priori asymmetric construction, not a
post-result choice.

Legal base edges are scanned lexicographically. An edge is accepted only when
it is endpoint-disjoint from prior accepted edges, introduces a new sorted
endpoint-valence pair, and has new radius-1 and radius-2 neighborhood
signatures; the first three accepted edges are `(0,2)`, `(3,4)`, and `(6,8)`.
For radius `R`, graph distance is the minimum distance from either endpoint.
The signature records, for every shell `0..R`, the sorted per-vertex tuple of
base valence, neighbor counts in every shell, and neighbor count outside the
radius; it also records edge counts by shell pair, the endpoint valence pair,
and the two opposite-vertex valences. Each signature is stored in
`family_metadata.json` and the matching member metadata and is recomputed by
tests. The three signatures must be pairwise different independently at both
radii.

Each member replaces exactly the two incident faces of its accepted edge and
introduces one previously absent diagonal. `family_metadata.json` is
authoritative for locality. An unchanged face retains `base-face-NNNN` only
when its CSV row and oriented vertex triple are byte-for-byte the base values.
Each rewritten row receives a variant-local ID and is explicitly non-identical;
inventing correspondence between the two different triangular domains is
forbidden. The metadata lists the old/new edge, quadrilateral boundary cycle,
both rewritten rows and faces, and every unchanged base/member row pair.

The hash-covered `locality_sample_manifest` contains exactly ten interior
points. Its denominator is 6; enumerate total numerator `s=2,3,4,5`, then
`i=1,...,s-1`, set `j=s-i`, and use
`(u,v)=(i/6,j/6)` with barycentric numerators `(6-i-j,i,j)`. The sample ID is
`tri-l6-sSS-uII-vJJ` with two-digit numerators. This order is mandatory, as is
the row order `position,du,dv,duu,duv,dvv`. Every listed comparable unchanged
face uses every sample exactly once at the same oriented face-local `(u,v)` in
base and member; there is no corner permutation and no per-corner duplication.

The valence-7/8/9 fixture reuses the seeded embedded convex hull and declares
vertices 2, 4, and 0 for valences 7, 8, and 9 respectively. Its frozen,
scale-invariant triangle quality is
`Q=4*sqrt(3)*area/(a^2+b^2+c^2)` with `min(Q) >= 0.24`; generation and an
independent test require finite coordinates, positive triangle areas, and zero
intersections between triangles with disjoint vertex sets. Metadata records the
observed minimum and intersection count. The adjacent-extraordinary fixture is
the closed oriented octahedral sphere after one legal flip; the new edge joins
two recorded valence-5 vertices.

That reuse is byte identity, not independent corroboration: the
`b2p_valence789` `vertices.csv` and `faces.csv` are deliberately byte-for-byte
identical to the single-flip family's base files. The shared hull supplies one
mesh-level oracle/geometry observation. The valence-7/8/9 label identifies the
declared high-valence corners, while the family contributes three distinct
topological interventions for locality. B2 must expose the shared content
hashes and must not count the two directory names as independent mesh-level
corroboration in any aggregate, sample count, or conclusion.

The shared hull deliberately has valences
`[3,3,4,4,4,4,5,5,5,5,7,8,9]` and therefore no valence-6 vertex at depth zero.
Consequently none of its coarse corners satisfies section 3.2's isolation rule;
coverage depends on recorded refinement reaching isolation by depth 12, and a
miss remains oracle-uncovered. Its valence-3 corners also retain the difficulty
surfaced by the archived PR 182 evidence rather than selecting it away. This is
a frozen negative-evidence risk to accept explicitly with D10, not grounds to
weaken a target, replace the fixture after results, or count an uncovered item.

All members are generated by `scripts/generate_b2p_loop_fixtures.py` using only
the Python standard library. Each metadata file records generator/version/
parameters, source identity, vertex/edge/face counts, valence facts, complete
vertex use, duplicate-face absence, exact two-face edge incidence, opposite
edge directions, and connected degree-2 vertex links. Checked-in files must
reproduce byte-for-byte in a fresh temporary output root.

## 8. Gate sequence

```text
B0a inventory logic repair              (blocks everything; may start now)
  |
  +-- B0b inventory CI enforcement      (after B0a merges GREEN)
  +-- B0c record D1 + D2 approvals      (after B0a; D1/D2 approved 2026-08-06)
  |
  +-- WP1.1a legacy index safety        (L1; disjoint files; may run parallel)
  |
  +-- B1 topology key / row contract amendment   (no OpenSubdiv include at all)
        |
        +-- B2p preflight: freeze D10, oracle contract, fixtures, face
        |     correspondence, row-comparison tolerance     [T2]
        |     + explicit user D10 approval
        |
        +-- B2 Bfr qualification proof against the frozen inputs   [T2]
              |     (Far runs only as a regression comparator)
              |
              +-- explicit user D9a: Bfr PASS or FAIL
                    |          \
                    |           `-- FAIL: lane BLOCKS, escalate to a new
                    |               architecture decision. No Far fallback.
                    |
                    +-- B3 Bfr full-mesh provider   [T2]
                          |   (owns the exact-version 30700 pin)
                          +-- B4 topology epoch cache and invalidation
                                |
                                +-- unified plan WP4 -> WP5
                                      |
                                      +-- WP5.2 quadrature selected
                                            |
                                            +-- D9b Bfr production activation
                                            +-- WP6 -> WP7  (WP8 CUDA by
                                                separate explicit instruction)

Independent lanes, neither blocked by nor blocking the B lane:

L4 stack disposition (PR 185 -> close 176/182), on explicit user instruction.

L7 topology ownership and rebuild transaction  --> REQUIRED BEFORE WP9
  (disjoint files; may run parallel with the whole B lane)
      |
      +-- WP9 adaptive edge flipping   (separate explicit instruction)
      +-- L8 optional custom Bfr mesh adapter, Phase-2 localized invalidation

B2 outcome 2 (Bfr not qualified) blocks B3. It routes to a new explicit
architecture decision - options include WP5.1's patch-domain candidate, a
different representation, or a separately gated package to harden Far - and never
to an automatic Far fallback or a configuration change.
```

D3, D4, D5, D2b, and D8 keep the authority the ADR already assigns them.
Nothing in this plan decides them.

## 9. Checkpoint ledger

| Checkpoint | Deliverable | Status | Required approvals |
| --- | --- | --- | --- |
| KB0a | Baseline inventory passes at main and at a merge-bearing descendant | Ready; user chose option (b), supersede PR 186 | T1 technical |
| KB0c | D1 and D2 recorded as approved with their scope limits | Pending KB0a | T1 technical |
| KB0b | Inventory enforced by a CI workflow, OpenSubdiv-free and read-only | Pending KB0a green | T1 technical |
| KB1 | Extended `LoopTopologyKey` and row contract, no OpenSubdiv include | Pending B0a, B0b, B0c | T1 technical |
| KB2p | Frozen D10 targets, oracle contract, new fixtures and hashes, face correspondence | Merged as PR 193 at `b8ed8bd2dbbf994a4419695cf490b2a3e6f349a6`; D10 approved 2026-08-08 | T2 + explicit user D10 |
| KB2r | B2-readiness budgets plus complete section-8/section-7 fixture execution manifest | Drafted independently; no candidate run; pending technical/scientific review and explicit user D12 | T2 + explicit user D12 |
| KB2 | Bfr qualification evidence against B2p's and D12's frozen inputs; Far comparator results published | Stopped before edits until KB2r merges and D12 is approved | T2: verification + technical + scientific + gatekeeper + user D9a |
| KB3 | Bfr full-mesh provider; owns the exact 30700 pin and the no-Far-in-production tests | Pending D9a PASS | T2 |
| KB4 | Topology epoch cache, invalidation, flip-pair re-preparation cost | Pending B3 | Technical |
| KB9b | D9b Bfr production-activation acceptance on integrated-functional evidence | Deferred to after WP5.2 | Scientific + explicit user |
| KL1 | WP1.1a merged; L1 quarantine still pending D5 | Ready now | T1, then T2 for WP1.1b |
| KL4 | PR 185 merged, PR 176/182 closed as superseded, D0 resolved | Pending explicit user instruction | User |
| KL7 | Topology ownership and rebuild transaction; **required before WP9** | Not started; independent of the B lane | T2 + explicit user |
| KL8 | Optional custom Bfr adapter, Phase-2 localized invalidation | Optional, strictly after KL7 | User |

## 10. What this plan does not authorize

Production activation; a new scientific baseline; a default backend change;
merging or closing PR 175, 176, 182, 185, or 186; deleting any legacy route;
changing CUDA; deciding D0 through D8; deciding D9a or D9b; ranking Bfr against
Far on near-vertex accuracy; promoting Far to a production evaluator by any means
short of a new explicit architecture decision and package; implementing a custom
Bfr mesh adapter; or any edge-flip mutation of `Mesh`.
