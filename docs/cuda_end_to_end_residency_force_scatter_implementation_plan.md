# CUDA End-to-End Device Residency And Force/Scatter Implementation Plan

Date: 2026-08-02.
Planning baseline: `origin/main` at
`93b18c683a19e3c35b595e8c85ae111b04caa967` (merge of PR #161).

This document is the implementation contract for work after the completed CUDA
proof of concept. It is deliberately written as a set of prompt-ready work
packages. A new implementation task should receive exactly one numbered work
package, its prerequisites, and the shared rules in this document. No task may
silently absorb a later package.

This planning PR changes no production source, build target, dependency,
backend route, force formula, floating-point policy, optimizer behavior,
dynamics behavior, checkpoint/output schema, or scientific result. Production
CUDA routing remains disabled.

## Decision Summary

The PoC supports further work, but only as an end-to-end residency program:

- The RTX 4050 Laptop GPU executes the isolated weighted-sample kernels much
  faster than the CPU after data is resident.
- At 1,048,576 proof batch items, kernel-only CUDA was `17.07x` faster than the
  serial comparator and `5.03x` faster than eight-thread OpenMP.
- Copy-inclusive CUDA was only `0.439x` as fast as eight-thread OpenMP because
  transfers consumed about `175.3 ms` of `188.95 ms`.
- The persistent-residency adapter crossed the eight-thread OpenMP comparator
  at four repeated resident iterations for both measured face counts. At 64
  iterations it reached `5.149x` for 4,096 faces and `4.752x` for 32,768.
- Forward and transpose differences remained below `8.89e-15`, and a dry run
  through the real CPU regular-face formula produced finite, nonzero forces.

Those results justify an opt-in production-shaped implementation. They do not
justify enabling a CUDA route. The PoC did not implement the complete force
formula, topology ownership, deterministic mesh scatter, regularization,
coordinate propagation, trial rollback, fallback, or atomic publication.

The selected design is therefore:

1. one persistent device state per eligible mesh;
2. a single ordered stream in the first implementation;
3. device-resident current/accepted coordinates, force families, face
   observables, and reduction workspaces;
4. full regular-face physics on the GPU, not only `W * p` and `W^T * g`;
5. deterministic source-keyed scatter by precomputed incidence and fixed-order
   segmented reduction, with no floating-point atomics in the initial route;
6. candidate-state computation followed by validation and atomic publication;
7. device-side line-search trial, commit, and rollback so repeated evaluator
   calls do not round-trip mesh-sized state; and
8. whole-evaluation CPU fallback decided before any CUDA-visible mutation.

## Non-Goals And Frozen Boundaries

The first production-capable lane does not:

- make CUDA a required build or runtime dependency;
- change default Make targets or invoke `nvcc` from a non-CUDA target;
- replace the CPU serial or OpenMP paths;
- enable CUDA automatically based only on device presence;
- support mixed CPU/GPU faces in one evaluation;
- use floating-point `atomicAdd` for scientific force or energy accumulation;
- enable `--use_fast_math`, reduced precision, TensorFloat-32, or relaxed math;
- change shape functions, quadrature order, force equations, boundary meaning,
  global constraints, regularization equations, or energy accounting;
- route the 11-control subdivision path, guarded valence-4/OpenSubdiv path, or
  valence-5 Option B path through CUDA;
- accelerate scaffolding, Gag, idealized-lattice, thermal/Metropolis, insertion
  topology mutation, or the dynamic `matMesh`/`matSurface` workflow;
- change output/checkpoint cadence or schema; or
- claim a production speedup from a surrogate or kernel-only benchmark.

Any one of these may become a later, separately approved program. Until then,
an enabled unsupported feature makes the mesh ineligible before evaluation.

## Required Reading For Every Implementation Task

Before editing, read these files and refresh any source anchors that moved:

- `docs/cuda_poc_implementation_plan.md`;
- `docs/cuda_regular_weighted_sample_benchmark.md`;
- `docs/cuda_regular_face_adapter.md`;
- `docs/force_formula_scatter_equivalence.md`;
- `docs/energy_force_evaluator_side_effect_boundary.md`;
- `docs/energy_force_evaluator_callsite_inventory.md`;
- `docs/irregular_valence4_production_scatter_buffer.md`;
- `src/energy_force/Compute_energy_and_force_on_mesh.cpp`;
- `src/energy_force/Force.cpp`;
- `src/model/Energy_minimization.cpp`;
- `src/Run_flat.cpp`; and
- the `Vertex`, `Face`, `Mesh`, `Param`, `Energy`, and `Force` declarations.

Run the existing inventories before relying on their maps. If the maps and the
source disagree, stop implementation and repair the plan in the same PR or a
prerequisite planning PR. Do not implement from stale line numbers.

## Existing Production Contract

`evaluate_energy_force(mesh)` currently reaches
`Mesh::Compute_Energy_And_Force()`, which performs these visible phases:

```text
1. refresh per-face area/volume and global Param::area/Param::vol
2. clear current vertex forces and face energies
3. evaluate membrane faces and scatter curvature/area/volume forces
4. compute regularization energy, force, and deformation counts
5. calculate vertex total force
6. totalize face energies and Param::energy, including global constraints
7. optionally apply scaffolding/harmonic/Gag/lattice energy and forces
8. zero or constrain boundary and ghost forces
```

The CUDA route is not complete unless it accounts for every phase allowed by
its eligibility matrix. A membrane-only result must never be published as a
complete evaluator result.

The current regular force formula consumes three quadrature samples, seven
weighted rows, 12 one-ring controls, and three coordinate axes. The row order
is fixed:

```text
0 x, 1 a_1, 2 a_2, 3 a_11, 4 a_22, 5 a_12, 6 a_21
```

For local control row `j`, the formula emits bending, area, and volume force
components. Production scatter addresses the destination with:

```text
source_id * 9 + force_family * 3 + axis
```

where families `0`, `1`, and `2` mean curvature/bending, area, and volume.
Current OpenMP uses one flat buffer per CPU thread and reduces buffers in
ascending thread index. Boundary faces are skipped in membrane accumulation;
ghost faces are skipped in geometry refresh. Face curvature energy, mean
curvature, and normal are output-visible side effects.

The optimizer also makes residency part of correctness. Line search repeatedly
forms a trial coordinate state from `coordPrev`, evaluates it, accepts or
rejects it, and may restore the previous state. Accepted coordinates, current
and previous forces, face energy, `Param::energy`, and NCG direction then feed
later iterations, records, outputs, and checkpoints.

## Hard Invariants

Every work package must preserve these invariants.

### Scientific invariants

1. Use `double` throughout production numerical buffers and kernels.
2. Preserve sample, row, local-control, force-family, and source-id mappings.
3. Preserve both mixed derivative rows; do not fold rows 5 and 6.
4. Preserve `0.5 * gaussQuadratureCoeff(q, 0)` accumulation in sample order.
5. Preserve current boundary-face and ghost-face exclusion rules.
6. Preserve all current face observables and all current force families.
7. Preserve global area/volume constraint inputs and energy-totalization order
   unless a separate scientific rebaseline explicitly approves a difference.
8. Reject nonfinite inputs, intermediates, outputs, and scalar decisions.
9. Repeated execution from identical device state must be bitwise stable on
   the same supported GPU/toolchain configuration.
10. CUDA-versus-CPU acceptance starts at maximum absolute error `1.0e-12` for
    every component. A relative metric is diagnostic only. A wider tolerance
    requires a separate scientific decision PR.

### State invariants

1. Host and device authority must be explicit for every resident field.
2. No failed CUDA evaluation may leave partially published host or device
   scientific state.
3. Rejected line-search or thermal trials must restore the exact accepted
   coordinate generation and invalidate all candidate-derived outputs.
4. A topology or shape-plan change invalidates every dependent device buffer.
5. Checkpoint/output consumers see a coherent accepted state, never a mix of
   accepted coordinates and trial forces.
6. CPU fallback begins from authoritative host state and is selected before a
   CUDA transaction mutates candidate state.
7. Device loss after a transaction starts is an error, not an implicit retry
   from uncertain state. An explicit recovery path may retry on CPU only after
   it proves that authoritative accepted host state is intact.

### Compatibility invariants

1. `make`, serial, OpenMP, dynamics, tests, and non-CUDA CI remain usable
   without CUDA headers, libraries, `nvcc`, or a GPU.
2. CUDA is compiled and selected only through an explicit opt-in.
3. Existing CPU behavior and tests remain the control baseline.
4. Public headers used by non-CUDA builds expose no CUDA type.
5. Runtime logs use the project diagnostics interface; library code must not
   add unconditional stdout noise.
6. Existing restart V1/V2 compatibility remains intact.

## Target Architecture

### Control plane and data plane

Keep orchestration in host C++ and numerical state in a CUDA implementation
hidden behind a non-CUDA interface. Suggested responsibilities are:

```text
EnergyForceEvaluator / Model host control plane
  -> eligibility and route decision
  -> begin candidate transaction
  -> request geometry/force/energy evaluation
  -> retrieve only decision scalars when possible
  -> commit, rollback, or synchronize for a named consumer

CudaDeviceContext (one CUDA device)
  -> device selection and capability checks
  -> stream, events, error translation, allocation policy
  -> no mesh-specific scientific state

CudaMeshState (one mesh, hidden implementation)
  -> topology and row-plan buffers
  -> accepted/current/candidate coordinates
  -> face observables and force-family buffers
  -> deterministic scatter incidence and workspaces
  -> energy and optimizer scalar reductions
  -> generation counters, dirty state, and transaction status
```

The names are suggestions, not a requirement. The ownership split is a
requirement. `Mesh` may own a backend-neutral handle or the evaluator may own a
registry keyed by stable mesh identity, but the design must prevent accidental
copying, aliasing between meshes, use after mesh destruction, and CUDA types in
ordinary headers. Prefer an owning `unique_ptr` to an incomplete implementation
or another RAII boundary with explicit move/copy policy.

### State classes and authority

Classify each resident field before implementation:

| Class | Examples | Normal authority | Invalidation |
| --- | --- | --- | --- |
| Immutable topology | face descriptors, one-ring source ids, boundary/ghost masks, vertex incidence offsets/entries | host at construction, then identical copies | mesh topology generation |
| Immutable numerical plan | regular weights, quadrature coefficients, reference coordinates, material-independent indexing | host at construction, then identical copies | shape/quadrature/reference generation |
| Mutable parameters | moduli, spontaneous curvature, global constraint values, boundary mode | host control plane, uploaded only when generation changes | parameter generation |
| Accepted dynamic state | accepted coordinates, previous forces/energy, NCG direction | device during eligible optimization, host at synchronization points | commit or host edit |
| Candidate dynamic state | trial coordinates and all trial-derived observables | device transaction only | every trial, rollback, or failure |
| Published observables | face geometry/energy/normal/curvature, force families, total force, global energy/area/volume | device until a named host consumer requires them | successful evaluation |
| Workspace | weighted rows, per-occurrence contributions, reductions, status flags | device only | capacity or topology change |

Every class needs a monotonically increasing generation or epoch. At minimum,
track topology, numerical-plan, parameter, accepted-coordinate, reference,
candidate, and allocation epochs. Debug builds should assert generation
dependencies before every launch. Release builds must return a structured
error rather than consume stale buffers.

### Required device buffer schema

Use contiguous, explicitly indexed arrays and document every stride in code and
tests. A structure-of-arrays layout is preferred for mesh-sized fields unless a
measured alternative wins without obscuring the contract. The minimum logical
schema is:

| Buffer group | Required logical fields |
| --- | --- |
| Vertex topology | vertex count; boundary/ghost masks; regular face-incidence offsets and canonical occurrence indices |
| Face topology | face count; boundary/ghost masks; 12 source IDs per eligible face; adjacent triangle IDs needed by regularization |
| Static numerical data | three-by-seven-by-12 weights, three quadrature coefficients, reference coordinates, and immutable material/indexing data |
| Coordinate state | accepted/current, previous, candidate, and reference `nVertices x 3` coordinates where the eligible algorithm distinguishes them |
| Membrane occurrences | `nEligibleFaces x 12 x 3 families x 3 axes` in canonical face/local/family/axis order |
| Current force state | curvature, area, volume, thickness, tilt, regularization, harmonic-bond, and total `nVertices x 3` arrays |
| Previous/optimizer force state | all checkpoint-visible previous force families and NCG direction families required by the eligible optimizer |
| Face observables | normal `x/y/z`, mean curvature, element area, legacy element volume, and all ten `Energy` channels |
| Global observables | area, volume, all ten `Energy` channels, deformation counts, force/direction reductions, force norms, and status |
| Control metadata | capacities, generations, active accepted/candidate buffer roles, eligibility/fallback reason, transfer counters, and first-error record |

Candidate initialization must reproduce the existing clearing phase: every
force and energy channel starts from defined zero, including eligible-route
terms that are disabled. Do not rely on a previous allocation's contents or on
an unsupported CPU feature to overwrite a stale value later.

### Allocation and stream policy

The first implementation uses one non-default stream per `CudaMeshState` and
explicit events only where a host decision is required. Allocate topology and
capacity buffers once, reuse them across evaluations, and grow geometrically
under checked byte arithmetic. Do not allocate or free in a per-face or
per-trial loop.

A reviewed implementation may use `cudaMallocAsync` and a memory pool when the
runtime/device reports support, but must have a simple compatible fallback and
must prove stream-ordered lifetime. It is acceptable to begin with persistent
`cudaMalloc` allocations made outside measured loops. Unified Memory and
zero-copy are not the default design; introduce them only with evidence.

Calculate every buffer size with overflow-checked `size_t`. Before allocation,
report required, free, and total bytes and enforce the existing conservative
50%-of-current-free-memory PoC budget until a reviewer approves another limit.
Pinned host staging is allowed only for measured synchronization paths and must
be bounded because page-locked memory is a scarce host resource.

### Initial execution DAG

For an eligible regular-only evaluation, one ordered stream executes:

```text
ensure topology/plan/parameter generations are current
  -> form or select candidate coordinates
  -> enforce candidate coordinate boundary/ghost mapping
  -> per-face geometry kernel
  -> deterministic area/volume reductions
  -> per-face regular weighted rows and complete membrane formula
  -> write face candidate observables
  -> write canonical per-occurrence force contributions
  -> deterministic source-keyed scatter reduction
  -> regularization contributions and deterministic reduction
  -> calculate all eligible vertex force families and forceTotal
  -> deterministic face/global energy reductions
  -> apply force boundary/ghost mask in current production order
  -> validate status, finiteness, cardinality, and generations
  -> expose decision scalars or publish the coherent candidate
```

Do not launch a host callback that mutates `Mesh`. Host publication is an
explicit synchronized operation owned by the control plane.

## Complete Regular-Face Formula Design

The production kernel must port the actual regular-face bending, area, and
volume computation in `Mesh::element_energy_force_regular`, not call the PoC
transpose as a substitute. Keep a single documented mapping from packed
device arrays to production names.

Recommended first shape is one CUDA thread per face. Each thread:

1. gathers 12 coordinates through the packed one-ring source IDs;
2. evaluates the seven weighted rows for each of three samples;
3. derives `a_3`, `a_31`, `a_32`, contravariant bases, curvature terms, and
   constraint terms in the same mathematical sequence as the CPU formula;
4. accumulates face area/volume/curvature energy, mean curvature, and normal;
5. writes 12 occurrences by three force families by three axes in canonical
   `(face_index, local_control, family, axis)` order; and
6. records the first structured status error instead of publishing NaN/Inf.

Keep the formula available as a host/device-testable numerical unit where
practical. Build comparison tests from simple intermediates outward: weighted
rows, per-sample geometry, per-sample force terms, face totals, and finally
mesh scatter. A face-level mismatch should not require debugging only the final
global force vector.

Do not fuse scatter into the formula kernel in the first implementation. The
explicit occurrence buffer is a correctness seam, supports independent
oracles, and prevents scheduling-dependent updates.

## Deterministic Force/Scatter Design

### Selected algorithm

Use a topology-time compressed incidence plan and evaluation-time fixed-order
reduction.

Topology packing emits canonical contribution occurrences in ascending
`face_index`, then ascending `local_control`. Each occurrence stores its source
vertex ID or is already grouped through a stable permutation. Build:

```text
source_offsets[nVertices + 1]
source_occurrences[nOccurrences]
```

For vertex `v`, entries in
`source_occurrences[source_offsets[v] : source_offsets[v+1]]` must appear in
canonical face/local-control order. The same source vertex appearing in many
faces is normal: each face/local occurrence contributes once and is retained in
order. A repeated source ID within one regular face is rejected by topology
preflight unless a separately reviewed topology contract proves it valid; the
initial route must not silently reinterpret malformed one-rings.

Construct the incidence plan on the host with a checked deterministic
two-pass algorithm: validate and count occurrences per source, exclusive-scan
the counts with overflow checks, then refill per-source cursors by visiting
faces and local controls in canonical order. Validate that offsets start at
zero, are monotonic, end at the exact occurrence count, and that every
occurrence appears exactly once before any device upload. Keep an independent
test oracle that groups `(source, face, local)` tuples without calling the
production builder.

The formula kernel writes:

```text
face_contrib[(face * controls_per_face + local) * 9 + family * 3 + axis]
```

The first scatter kernel assigns one deterministic writer to each
`(source_vertex, family, axis)` and visits that vertex's incidence entries in
the stored order using `double`. This eliminates floating-point atomics and
makes the result independent of block scheduling. If a vertex incidence list
is too large for one practical writer, a later fixed-shape two-pass reduction
may be used only if its tree and chunk order are frozen and tested.

### Numerical contract

The GPU reduction order is a new explicitly defined order. It cannot generally
be bitwise equal to every OpenMP run because the current CPU face-to-thread
assignment determines intermediate grouping. Therefore:

- leave the CPU implementation and its thread-buffer order unchanged;
- compare CUDA against the explicit serial CPU oracle with the `1.0e-12`
  component gate and report comparisons against supported OpenMP thread counts;
- require bitwise equality across at least 20 identical CUDA repetitions on
  the same supported device/toolchain;
- record maximum absolute and relative differences separately for curvature,
  area, volume, regularization, total force, and energy/geometry observables;
- test cancellation-heavy and permuted-source fixtures; and
- never widen tolerance merely to hide an uncharacterized reduction change.

### Required scatter fixtures

Cover at least:

1. one regular face with natural one-ring order;
2. one regular face with deliberately permuted source order;
3. several faces sharing source vertices;
4. repeated source IDs within one synthetic face, with exact preflight
   rejection and no partial incidence publication;
5. isolated vertices with zero incidence;
6. boundary and ghost vertices;
7. cancellation-heavy signed contributions;
8. malformed offsets, out-of-range IDs, overflow cardinality, and nonfinite
   contribution rejection; and
9. a representative closed regular mesh checked against serial and OpenMP.

The production GPU route must use this reviewed reducer. A high-performance
atomic alternative is a separate experiment and cannot replace it in the same
PR.

### Deterministic scalar and face reductions

Global area, volume, energy, force-dot-direction, and force-norm reductions
also need a frozen order. Use a documented fixed-width tree over contiguous
input ranges: each first-pass block owns a fixed range, shared-memory stages
combine fixed index pairs, and later passes reduce partials with the same rule
until one value remains. Freeze the block width as part of the numerical
contract and pad missing leaves with positive zero. Each block writes one
unique partial; no floating-point atomic may update the final scalar.

Integer deformation counts may use exact integer reduction after proving no
overflow. Do not rely on an external reduction primitive unless its ordering
and version/architecture stability satisfy the same tests. Record the chosen
tree shape in machine-readable metadata because changing it is a numerical
rebaseline, not a transparent tuning change.

## Candidate Transaction And Publication

Treat an evaluation or optimizer trial as a transaction with these states:

```text
IdleAccepted -> CandidatePrepared -> Computing -> Validated
             -> Committed -> IdleAccepted
             -> RolledBack -> IdleAccepted
             -> Failed (accepted state remains authoritative)
```

Candidate buffers must be distinct from accepted state where rollback can
occur. Coordinate double-buffering is preferred: accepted coordinates are
never overwritten by a line-search trial. Derived candidate outputs may reuse
workspace only after the previous transaction completes.

Commit swaps or advances buffer roles and generations; it must not copy a full
mesh solely to commit. Rollback discards the candidate generation and selects
the accepted coordinate buffer. A failure records an error and invalidates the
candidate; it must not mark candidate observables current.

Host publication is also transactional:

1. validate CUDA status and all required output buffers;
2. copy into temporary host staging arrays;
3. validate cardinality and finiteness again at the API boundary;
4. publish all vertex, face, and `Param` fields as one control-plane action;
5. mark the host generation coherent only after all publications succeed.

Never write directly into individual `Vertex` or `Face` objects as asynchronous
copies complete. Shadow mode must compare staging arrays without mutating the
CPU control result.

## Optimizer Residency Boundary

The first performance-eligible workflow is the regular-only, scaffold-disabled,
thermal-disabled `run_flat` line-search path. Port only the mesh-sized operations
needed to keep its repeated trials resident:

- form trial coordinates from accepted/previous coordinates, step size, and
  NCG direction;
- enforce fixed/free/periodic coordinate rules exactly;
- run the complete eligible evaluator DAG;
- reduce force-dot-direction and force-norm-squared scalars;
- return energy and decision scalars to the host;
- commit or roll back through the transaction API;
- update previous force and NCG-direction arrays on device when a step is
  accepted; and
- synchronize accepted state only for a named output, record, checkpoint,
  unsupported operation, or final result.

Line-search policy remains host-owned in the first route. Transferring a few
scalars per trial is acceptable; transferring coordinates, forces, weighted
rows, or face arrays per trial is not.

Reference-coordinate updates are explicit generation events. Periodic output
and checkpoints request a coherent accepted-state download. `Record` may
consume reduced area, energy, and mean-force scalars without downloading all
forces. Instrument every download with a reason enum so transfer regressions
are visible.

Do not route `run_dynamics_flat` in this program phase. Its `matMesh`,
`matSurface`, `mesh2surface`, `surface2mesh`, and host/vector synchronization
form a separate residency boundary. Do not route thermal trials until RNG
state, proposal generation, Metropolis rollback, and checkpoint reproducibility
have their own approved device-state contract. Do not route scaffolding until
membrane/scaffold force and energy ownership are designed together.

## Eligibility, Fallback, And Failure Policy

### Initial route eligibility

All conditions must pass before starting a CUDA transaction:

- CUDA was compiled by an explicit opt-in target;
- the user selected the CUDA backend explicitly;
- a compatible device, driver/runtime combination, required `double`
  capability, grid sizes, and required memory are available;
- every evaluated physical face uses the supported 12-control regular plan;
- no unsupported irregular or OpenSubdiv route is requested;
- no scaffold, Gag, idealized-lattice, thermal/Metropolis, or dynamic-mesh
  feature is enabled;
- topology, indices, weights, parameters, coordinates, and reference
  coordinates pass validation;
- the boundary mode is one of the modes proven by the current package; and
- no prior unrecovered CUDA error exists for the state.

Insertion may be allowed only if it changes already-resident per-face values
without changing topology and a focused test proves its semantics. Otherwise
it is initially ineligible.

### Fallback rules

- Backend `cpu`: always use the existing CPU route.
- Backend `cuda`: fail loudly if eligibility is not met; do not silently
  change scientific/backend intent.
- Backend `auto`, if introduced later: decide once before mutation and emit a
  structured reason for selecting CPU. `auto` must remain a separate reviewed
  feature and must not be smuggled into the first activation PR.
- A mesh may return to CPU only after synchronizing a coherent accepted state.
- No per-face hybrid fallback is allowed in the first implementation.
- No CUDA error after candidate computation begins triggers silent CPU retry.

Use stable structured result codes such as unavailable device, unsupported
topology, unsupported feature, stale generation, memory budget, invalid input,
kernel status, nonfinite result, transfer failure, and synchronization failure.
Messages must include the operation and CUDA error string without leaking
uninitialized data.

## Validation Matrix

### Unit and component gates

Each package adds dependency-free tests for host contracts and CUDA tests that
skip explicitly when CUDA is unavailable. CUDA-required evidence runs with a
`--require-cuda` equivalent and fails instead of skipping.

Required component comparisons include:

| Surface | Required comparison |
| --- | --- |
| Packed topology and row plans | exact integer/cardinality/order equality |
| Weighted rows | maximum absolute delta `<= 1.0e-12` |
| Per-sample geometry/formula terms | maximum absolute delta `<= 1.0e-12` |
| Face area, volume, curvature energy, mean curvature, normal | per-component delta `<= 1.0e-12`, finite |
| Curvature/area/volume occurrence contributions | per-component delta `<= 1.0e-12`, finite |
| Scatter result | per-family/per-axis delta `<= 1.0e-12`, 20-run CUDA bitwise repeatability |
| Regularization and deformation count | force/energy delta `<= 1.0e-12`; count exact |
| Total force and total energy | per-component/channel delta `<= 1.0e-12`, finite |
| Trial commit/rollback | exact generation and buffer-role behavior; accepted state unchanged on rollback |
| Host publication | all-or-nothing mutation, exact field coverage |

Also use conservation and structural checks where applicable: summed internal
force, equal occurrence/scatter totals in a higher-precision oracle,
face/source cardinality, boundary zeroing, and energy channel totalization.

### End-to-end scientific gates

Before activation, run deterministic representative workflows through CPU
serial, supported OpenMP thread counts, CUDA shadow, and CUDA publish modes.
Compare at every accepted iteration and at every rejected trial:

- coordinates and previous coordinates;
- current/previous force families and NCG direction;
- all face observables and energy channels;
- `Param::area`, `Param::vol`, all energy channels, deformation counts, and
  line-search decisions;
- accepted/rejected status and selected step size;
- record values; and
- V2 checkpoint plus output-visible state after forced synchronization.

The initial route may use the `1.0e-12` component gate, but trajectory-level
drift needs a separately reviewed policy before default enablement. Do not call
two trajectories equivalent only because their final energy is similar.

### Negative and recovery gates

Inject failures at allocation, copy, kernel status, validation, and publication
boundaries. Prove that:

- accepted state remains coherent;
- host publication is unchanged after rejection;
- CUDA-only mode reports a stable error;
- explicit recovery synchronizes or fails without guessing; and
- a subsequent independent CPU evaluation still matches its baseline.

### Compatibility gates

Every PR runs:

- its focused Python/C++ tests;
- plan and source-anchor inventories;
- default non-CUDA build and test targets;
- serial and OpenMP regression tests;
- CUDA-unavailable skip behavior where relevant;
- `git diff --check`; and
- the repository's currently documented expected-failure audit, distinguishing
  pre-existing failures from new failures.

## Performance Acceptance

Do not benchmark until correctness gates pass. Report serial CPU, eight-thread
OpenMP, CUDA kernel/DAG time from events, synchronization time, transfer bytes
and time by reason, allocation time outside the loop, and complete workflow
wall time. Use warm-ups and at least 30 measured repetitions; report median and
p95, not best-of-N.

The production recommendation requires all of:

1. transfer-inclusive speedup greater than `1.0x` over the same eight-thread
   OpenMP workflow on a representative real SLIMED run;
2. no mesh-sized host/device transfer inside the repeated line-search trial
   loop except a specifically justified diagnostic shadow run;
3. no per-trial allocation after capacity warm-up;
4. recorded device, driver/runtime, compiler flags, CPU/OpenMP topology,
   affinity, power mode, seed, mesh size, face class, iteration/trial counts,
   and memory high-water mark;
5. stable correctness at the measured configuration; and
6. a documented break-even region, including cases where CPU remains faster.

Profile only after an end-to-end timing gate identifies a bottleneck. CUDA
Graphs, multiple streams, kernel fusion, pinned-memory expansion, alternative
layouts, or atomics each require focused evidence and may not be bundled into
route activation.

NVIDIA's current guidance emphasizes minimizing host/device transfers and
keeping intermediate structures on the device. It also warns that pinned
memory is scarce and should be measured, and documents the stream-ordering
requirements of asynchronous memory pools. Treat those as design inputs, not
as evidence that a particular optimization helps SLIMED:

- <https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/index.html#data-transfer-between-host-and-device>
- <https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/stream-ordered-memory-allocation.html>
- <https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/cuda-graphs.html>

## Staged PR Program

Each numbered step is one branch, one focused PR, and one implementation task.
The next step starts only after the current PR is reviewed, approved by the
repository owner, and merged. If a step exposes a design flaw, repair or amend
the plan before continuing.

### Step 0 / PR 0: Plan and protected contract

- Add this plan, its dependency-free inventory, and tests.
- Confirm PoC conclusions and current production anchors.
- Do not modify production/build/CUDA source or enable a route.

Exit evidence: all protected architecture, correctness, compatibility,
performance, review, and prompt-package anchors are present and ordered.

### Step 1 / PR 1: Optional backend shell and capability report

- Add an explicit optional CUDA build target and non-CUDA stub.
- Add hidden RAII device/context/stream ownership with no scientific buffers.
- Add device/runtime/capability/memory reporting and structured errors.
- Prove default targets do not discover or invoke CUDA.
- Do not route an evaluator call or add a production kernel.

Exit evidence: clean CUDA-present and CUDA-absent behavior, lifetime/error
tests, and unchanged default serial/OpenMP builds.

### Step 2 / PR 2: Canonical mesh packer and eligibility preflight

- Pack regular topology, one-ring IDs, face masks, shape rows, quadrature,
  parameters, and reference coordinates into backend-neutral arrays.
- Build the stable source-incidence plan used by deterministic scatter.
- Implement the explicit eligibility matrix and exact diagnostic reasons.
- Add overflow, duplicate occurrence, permutation, boundary, ghost, and stale
  topology tests.
- Do not allocate GPU scientific buffers or route production.

Exit evidence: exact CPU round-trip from packed data and independent incidence
oracles for representative fixtures.

### Step 3 / PR 3: Persistent device state and transactions

- Add per-mesh device buffers, capacity management, epochs, dirty tracking,
  accepted/candidate coordinate double buffering, and commit/rollback.
- Upload only changed generations and instrument every transfer by reason.
- Enforce the memory budget and failure atomicity.
- Do not implement force formulas or publish into `Mesh`.

Exit evidence: transaction state-machine tests, injected allocation/copy
failures, exact rollback, no allocations in warmed repeated trials, and no
unexplained repeated transfers.

### Step 4 / PR 4: Regular geometry and global area/volume

- Port eligible regular per-face area/volume geometry.
- Add deterministic global area/volume reductions.
- Write only device candidate buffers and status.
- Compare face and global outputs against serial/OpenMP fixtures.
- Do not publish to production objects or implement force scatter.

Exit evidence: natural/permuted/curved/boundary/ghost/degenerate cases at the
fixed numerical gate and 20-run device repeatability.

Implementation status (2026-08-03): `codex/cuda-step4-geometry-reductions`
implements this slice without production routing or host publication. The
focused core uses production packed rows and compares against
`Mesh::calculate_element_area_volume()` at `1.0e-12`; the native RTX report
runs all six required fixtures through the actual kernel for 20 repetitions
each, binds every per-face/global/structural result, and proves no warmed
allocations plus balanced teardown. Kernel, diagnostic-copy, synchronization,
status, nonfinite, negative-area, and invalid-total failures leave the accepted
state recoverable. Final status
remains subject to the required pull-request review and owner merge approval.

### Step 5 / PR 5: Complete regular membrane force formula

- Port the actual weighted rows and full bending/area/volume formula.
- Emit face observables and canonical per-occurrence force contributions.
- Add intermediate-level diagnostics and nonfinite/degeneracy status handling.
- Keep scatter separate; do not write vertex force buffers.

Exit evidence: per-sample, per-face, per-occurrence, energy, curvature, and
normal parity against the actual CPU formula.

### Step 6 / PR 6: Deterministic source-keyed scatter

- Implement the reviewed incidence-based, fixed-order reduction into nine
  membrane force components per vertex.
- Preserve duplicate occurrences, zero-incidence vertices, and boundary inputs.
- Add cancellation and malformed-plan tests plus an independent higher-
  precision sum oracle.
- Do not use floating-point atomics or enable publication.

Exit evidence: serial/OpenMP parity within the fixed gate and bitwise-identical
CUDA results across at least 20 repeats.

### Step 7 / PR 7: Regularization, totals, and boundary completion

- Port or otherwise keep resident the regularization force/energy path,
  deformation count, total-force composition, face/global energy totals, and
  final force boundary/ghost handling for eligible configurations.
- Preserve all current phase ordering and output-visible channels.
- Do not support scaffolding or other excluded features.

Exit evidence: the complete eligible evaluator candidate equals CPU controls
for every published field, not just membrane forces.

### Step 8 / PR 8: End-to-end shadow evaluator

- Invoke the complete CUDA evaluator behind an explicit shadow-only mode.
- Run the existing CPU path as authority, compare every candidate field, and
  emit machine-readable mismatch/transfer/timing reports.
- Never publish CUDA results or change the selected CPU result.
- Exercise all call sites without changing their timing.

Exit evidence: multi-iteration shadow parity, failure injection, CUDA-missing
behavior, and zero CUDA mutations of authoritative host state.

### Step 9 / PR 9: Device-resident line-search operations

- Add device trial-coordinate formation, boundary coordinate enforcement,
  force-dot-direction, force-norm, previous-state updates, and NCG-direction
  operations needed by the eligible `run_flat` path.
- Return only decision scalars during trials.
- Bind accept/reject to device transaction commit/rollback.
- Do not route dynamics, thermal moves, scaffolding, or output ownership.

Exit evidence: accepted and rejected line-search traces match CPU decisions,
generations, energies, and step sizes, with no mesh-sized per-trial transfers.

### Step 10 / PR 10: Coherent host synchronization and publication

- Add named synchronization reasons for records, output, checkpoint,
  unsupported CPU work, explicit inspection, and final state.
- Publish all current V2-visible fields atomically from validated staging.
- Add transition back to CPU from coherent accepted state.
- Keep CUDA publish mode opt-in and non-default.

Exit evidence: exact field coverage, output/checkpoint compatibility, failed
publication atomicity, and unchanged CPU-only behavior.

### Step 11 / PR 11: Real-workflow benchmark and readiness decision

- Benchmark the actual eligible `run_flat` workflow, including accepted and
  rejected trials, records, and configured synchronization cadence.
- Report all correctness, transfer, allocation, memory, environment, median,
  p95, and break-even evidence.
- Compare serial, eight-thread OpenMP, CUDA shadow overhead, and CUDA publish.
- Make a written go/no-go recommendation; do not enable default routing.

Exit evidence: machine-readable results and a bounded recommendation for the
tested GPU/CPU/workload only.

### Step 12 / PR 12: Explicit opt-in route activation

Start this step only after a separate owner prompt approves activation based on
Step 11 evidence.

- Expose an explicit user backend choice with CPU as the unchanged default.
- Route only the proven eligibility envelope.
- Preserve loud CUDA-only failures and preflight CPU fallback policy.
- Add complete regression, documentation, and rollback instructions.
- Do not add automatic selection or expand feature eligibility.

Exit evidence: dedicated reviewer verdict, owner-approved scientific and
performance gates, clean CUDA/non-CUDA builds, and a reversible opt-in route.

## Shared Task And Review Protocol

Every implementation task must follow this exact protocol:

1. Start from current `main` after all prerequisite PRs are merged.
2. Create a focused `codex/cuda-residency-*` branch and record its base SHA.
3. Restate the assigned step, protected boundaries, and acceptance gates before
   editing.
4. Inspect the current source and dirty worktree; preserve unrelated user work.
5. Implement only the assigned step and update its contract/evidence docs.
6. Run focused tests, non-CUDA compatibility tests, inventories, and
   `git diff --check`; run CUDA-required evidence where the step requires it.
7. Commit, push, and open one ready PR against `main`.
8. Send the exact PR head SHA to the dedicated CUDA production reviewer task.
9. Require a verdict on scope, completeness, scientific correctness,
   compatibility/regression risk, evidence quality, and mergeability.
10. Fix blocking findings in the same PR and request re-review of the new head.
11. Stop and ask the repository owner for explicit approval to merge.
12. The implementation task and reviewer must not merge. Do not start the next
    step before the owner-approved merge is confirmed.

The dedicated reviewer should remain separate from implementation tasks and
review the exact head, not a moving branch. The reviewer must treat missing
CUDA hardware evidence as blocking only for steps whose exit gate explicitly
requires CUDA; it is never acceptable to turn a required CUDA run into a skip.

## Copy-Ready Master Prompt

```text
Implement exactly one step from
docs/cuda_end_to_end_residency_force_scatter_implementation_plan.md.

Assigned step: <STEP NUMBER AND TITLE>
Prerequisite merged PR/head: <PR AND SHA>
Dedicated reviewer task: <TASK ID OR LINK>

First read the complete plan and every file in its Required Reading section.
Refresh the source inventories and confirm the current main/base SHA. Restate
the assigned scope, non-goals, state authority, numerical gates, and exit
evidence before editing. Create a focused codex/cuda-residency-* branch.

Implement only the assigned work package. Keep production CUDA routing disabled
unless the assigned step is the separately owner-approved activation step.
Preserve default non-CUDA builds, the CPU serial/OpenMP control paths, all
scientific formulas and observable fields, and the PR-by-PR dependency order.
Do not use floating-point atomics, relaxed math, silent fallback, partial host
publication, or mesh-sized transfers inside resident trial loops unless this
step explicitly changes the reviewed contract.

Add focused tests and machine-readable evidence required by the step. Run the
focused suite, default non-CUDA compatibility checks, relevant serial/OpenMP
comparisons, CUDA-required checks when mandated, inventories, and git diff
--check. Document skipped or pre-existing failures precisely.

Commit and push one focused PR. Send its exact head SHA to the dedicated CUDA
production reviewer for scope, completeness, scientific correctness,
compatibility, regression risk, evidence, and mergeability review. Resolve all
blocking findings and request re-review. Do not merge and do not begin the next
step. Finish by asking the repository owner for explicit merge approval.
```

## Copy-Ready Step Addenda

Append exactly one of these blocks to the master prompt.

### Prompt addendum for Step 1

```text
Build only the optional backend shell: opt-in build target, non-CUDA stub,
hidden RAII device/context/stream ownership, structured capability report, and
error translation. Do not add scientific device buffers, kernels, evaluator
routing, or user-visible automatic backend selection. Prove that default
targets neither include CUDA headers nor invoke nvcc.
```

### Prompt addendum for Step 2

```text
Build the backend-neutral regular-only mesh packer, stable source-incidence
plan, and eligibility preflight. The incidence order must be ascending face
index then local control and must retain duplicate occurrences. Add exact
round-trip and invalid-input tests. Do not allocate scientific GPU buffers or
route an evaluator.
```

### Prompt addendum for Step 3

```text
Implement persistent per-mesh device storage and the IdleAccepted / candidate /
compute / validate / commit / rollback state machine. Track topology, plan,
parameter, accepted-coordinate, reference, candidate, and allocation epochs.
Instrument every transfer by reason and inject failures. Do not implement or
publish physics.
```

### Prompt addendum for Step 4

```text
Implement regular-face device geometry plus deterministic global area/volume
reductions into candidate buffers. Preserve ghost and boundary semantics and
compare to actual CPU geometry. Do not implement membrane force or publish
into Mesh.
```

### Prompt addendum for Step 5

```text
Port the complete actual regular bending/area/volume force formula. Emit all
face observables and canonical per-occurrence 12x9 force contributions. Build
intermediate-level CPU/CUDA comparisons. Do not fuse scatter, use atomics, or
write vertex forces.
```

### Prompt addendum for Step 6

```text
Implement only the deterministic incidence-based scatter/reduction. Assign one
deterministic writer to each source/family/axis, retain duplicate occurrences,
and sum in frozen incidence order. Require 20-run bitwise CUDA repeatability
and the fixed CPU parity gate. Do not use floating-point atomics or publish.
```

### Prompt addendum for Step 7

```text
Complete the eligible evaluator on device by adding regularization,
deformation-count reduction, forceTotal, face/global energy totalization, and
final boundary/ghost force handling in production order. Cover every eligible
output-visible field. Keep all excluded features ineligible and do not publish.
```

### Prompt addendum for Step 8

```text
Integrate the complete device candidate as a shadow evaluator behind an
explicit opt-in. CPU remains authoritative; compare every output field and
report mismatches, timings, and transfers in machine-readable form. Prove the
shadow cannot mutate authoritative Mesh state.
```

### Prompt addendum for Step 9

```text
Keep line-search mesh-sized state resident: trial coordinate formation,
boundary coordinate enforcement, evaluator calls, force/direction scalars,
accepted-state updates, and commit/rollback. Host retains decision policy and
receives scalars only. Do not route dynamics, thermal, scaffolding, or output.
```

### Prompt addendum for Step 10

```text
Implement named coherent synchronization and atomic host publication for all
V2-visible accepted state. Cover records, output, checkpoint, inspection,
CPU-transition, and final-state reasons. Publish mode stays explicit and
non-default. Inject transfer/publication failures and prove all-or-nothing
behavior.
```

### Prompt addendum for Step 11

```text
Benchmark the real eligible run_flat workflow. Include line-search trial loops,
accept/reject behavior, actual synchronization cadence, serial, eight-thread
OpenMP, CUDA shadow, and CUDA publish. Require correctness first, at least 30
timed repetitions, median/p95, transfer reasons/bytes, memory high-water, and a
bounded go/no-go recommendation. Do not activate routing.
```

### Prompt addendum for Step 12

```text
Activation has separate explicit owner approval: <APPROVAL REFERENCE>.
Expose only an explicit CUDA choice, retain CPU default, and route only the
proven regular-only eligibility envelope. Do not add auto selection or support
new features. Include rollback instructions and complete CUDA/non-CUDA
regression evidence.
```

## Dedicated Reviewer Prompt

```text
Act as the dedicated CUDA production reviewer for PR <NUMBER> at exact head
<SHA>. Read docs/cuda_end_to_end_residency_force_scatter_implementation_plan.md
and the assigned step. Inspect the complete diff and relevant current sources.

Return a mergeability verdict covering:
1. scope: the PR implements one step only and respects non-goals;
2. completeness: every step deliverable and exit-evidence item is present;
3. scientific correctness: formula/order/source mapping, state authority,
   determinism, tolerance, failure atomicity, and observable coverage;
4. compatibility: default non-CUDA, serial/OpenMP behavior, build/dependency,
   output/checkpoint, and unsupported-feature handling;
5. evidence: tests actually exercise the claims, required CUDA runs did not
   skip, metadata is complete, and pre-existing failures are distinguished;
6. integration risk: lifetimes, generations, transaction boundaries,
   synchronization, fallback, and regressions in other call paths.

List findings by severity with exact file/line references. Treat a stale PR
head, missing required evidence, silent fallback, partial publication,
floating-point atomics, relaxed math, unexplained mesh-sized trial transfers,
or production routing before Step 12 as blocking. If there are no blocking
findings, say exactly that the reviewed head is mergeable. Do not merge.
```

## Definition Of Program Completion

The implementation program is complete only when Step 12 is owner-approved,
reviewed, merged, and all of the following are true:

- CPU remains the default and CUDA remains optional;
- the proven eligible `run_flat` workflow keeps mesh-sized trial state on the
  device and transfers only named scalars/synchronization state;
- all eligible evaluator phases and output-visible fields are covered;
- deterministic scatter has no floating-point atomics and is repeatable;
- failed/rejected candidates cannot corrupt accepted host or device state;
- unsupported features are rejected or preflighted to CPU according to the
  explicit backend policy;
- real-workflow transfer-inclusive performance beats the documented OpenMP
  comparator in a bounded, reproducible region; and
- output, checkpoint, serial, OpenMP, CUDA-unavailable, and rollback behavior
  have reviewed evidence.

Until then, every CUDA production capability is experimental and opt-in, and
the existing CPU evaluator is authoritative.
