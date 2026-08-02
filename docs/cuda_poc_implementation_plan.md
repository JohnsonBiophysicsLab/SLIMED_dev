# CUDA Acceleration Proof-of-Concept Implementation Plan

Date: 2026-08-01.
Baseline: `origin/main` at `24cbc8c79259e4ee6dec039b87d816c03ea75560`
(merge of PR #152).

This is a proof-only CUDA lane. It does not change production C++ behavior,
default build targets, energy or force formulas, floating-point acceptance
policy, OpenMP scheduling or reduction order, OpenSubdiv dependency policy,
valence-5 architecture selection, checkpoint/output formats, optimizer or
dynamics behavior, RNG order, or production backend routing.

## Objective

Determine whether an NVIDIA CUDA backend can accelerate a numerically exact,
highly parallel slice of SLIMED's regular-face energy/force preparation without
making CUDA a required dependency or changing scientific results.

The first kernel boundary is the existing regular weighted-sample and transpose
shape documented by:

- `docs/opensubdiv_regular_sample_plan.md`;
- `docs/opensubdiv_mapping_contract.md`; and
- `docs/force_formula_scatter_equivalence.md`.

For batch item `b`, quadrature sample `q`, derivative row `r`, coordinate axis
`c`, and local control `j`, the forward proof computes:

```text
weighted[b,q,r,c] = sum(j=0..11) weights[q,r,j] * controls[b,j,c]
```

The transpose proof computes:

```text
controlGradient[b,j,c] =
    sum(q) sum(r=0..6) weights[q,r,j] * rowGradient[b,q,r,c]
```

This is the production-relevant `W * p` / `W^T * g` seam. The proof does not
replace `Mesh::element_energy_force_regular`, scatter into `Vertex::force`, or
route any face through CUDA.

## Observed Development Environment

The initial feasibility audit established:

- Windows NVIDIA driver `581.32`;
- WSL 2 with Ubuntu 26.04;
- NVIDIA GeForce RTX 4050 Laptop GPU;
- compute capability `8.9` and 6 GiB device memory;
- GCC 15.2;
- CUDA driver API 13.0; and
- CUDA 13.3 compiler/runtime development packages.

Proof binaries for this machine must emit native Ada SASS with
`-arch=compute_89 -code=sm_89`. They must not depend on PTX JIT because the
CUDA 13.3 runtime is operating through CUDA 13.x minor-version compatibility
with the 581-series driver.

The repository must remain usable when `nvcc`, a CUDA-capable GPU, or the CUDA
runtime is absent. CUDA discovery is opt-in, no default Make target may invoke
`nvcc`, and dependency-free inventory tests must remain runnable on ordinary
Linux and macOS CI hosts.

## Frozen Proof Data Shape

The first proof uses the current regular contract:

- three default quadrature samples in their existing order;
- seven derivative rows in their existing order;
- 12 local controls addressed by `Face::oneRingVertices[j]`;
- three double-precision coordinate or gradient components; and
- duplicated mixed-derivative rows 5 and 6.

Input and output buffers will be contiguous, explicitly sized arrays of
`double`. The standalone proof may choose an array-of-structures or
structure-of-arrays device layout, but it must preserve a single documented
index mapping and compare results after mapping them back to the frozen SLIMED
order.

The first implementation must not use global floating-point atomics. Each
output element must have one deterministic writer so repeatability can be
characterized independently from any later production scatter design.

## Correctness Gates

CUDA performance measurements are invalid unless all correctness gates pass:

1. A dependency-free CPU reference evaluates the same explicit sums in frozen
   `q`, `r`, `j`, and `c` order using `double`.
2. Every CPU and CUDA input/output component is checked for finiteness.
3. Forward and transpose outputs report maximum absolute and relative deltas.
   The initial maximum absolute acceptance gate is `1.0e-12`; it may not be
   widened without a separately reviewed scientific decision.
4. The independent adjoint identity
   `dot(g, W * p) == dot(W^T * g, p)` is checked with a long-double host oracle.
5. At least 20 identical CUDA repetitions must produce bitwise-identical
   outputs for the deterministic no-atomic kernel.
6. Natural and deliberately permuted control orders are covered. Duplicate
   source-id aggregation remains a host-side mapping contract until a later
   proof explicitly characterizes a device implementation.
7. Invalid dimensions, nonfinite inputs, CUDA API failures, and missing devices
   fail loudly with actionable diagnostics.

The proof report must include device name, compute capability, driver/runtime
versions, compiler version, compile flags, random seed, batch size, and all
correctness maxima. A passing generic vector-add smoke test is environment
evidence only and is not SLIMED correctness evidence.

## Performance Method

Performance evidence must distinguish computation from transfer overhead:

- serial CPU reference time measured with a monotonic host clock;
- OpenMP CPU comparator time where the proof workload is large enough to make
  it meaningful;
- CUDA kernel-only time measured with CUDA events after warm-up;
- host-to-device and device-to-host transfer times; and
- transfer-inclusive end-to-end CUDA wall time.

The harness will cover logarithmically increasing batch sizes, including small
batches that expose launch overhead and the largest batch that remains safely
within the 6 GiB device-memory budget. Each measured case uses warm-up runs and
at least 30 timed repetitions, reporting median and p95 rather than a single
best result.

An integration recommendation requires transfer-inclusive speedup greater than
one on a representative repeated SLIMED workload. Kernel-only speedup is not
sufficient. The report must identify the measured break-even batch size and
must not extrapolate beyond the tested GPU, power state, precision, or workload.

## Staged PR Sequence

Each step is a separate branch and PR. Work on the next step begins only after
the dedicated reviewer declares the current PR mergeable and the repository
owner approves its merge.

### Step 1 / PR 1: Plan and validation contract

- Add this implementation plan.
- Add a dependency-free inventory and tests for scope, environment,
  correctness, performance, and review gates.
- Do not add CUDA source or modify production/build files.

### Step 2 / PR 2: Forward `W * p` correctness proof

- Add an opt-in standalone `.cu` experiment for batched regular weighted
  samples.
- Add the explicit-order CPU reference and deterministic fixtures.
- Add a runner that skips with a clear reason when CUDA is unavailable.
- Leave all default Make targets and production paths unchanged.

### Step 3 / PR 3: Transpose `W^T * g` proof

- Add back-projection without floating-point atomics.
- Check the long-double adjoint identity, permutations, finiteness, and 20-run
  bitwise determinism.
- Keep duplicate source-id aggregation outside the device kernel unless that
  behavior is separately proven.

### Step 4 / PR 4: Comparative benchmark evidence

- Add serial CPU, OpenMP CPU, CUDA kernel-only, transfer, and end-to-end timing.
- Sweep batch sizes with warm-ups and at least 30 measured repetitions.
- Record median, p95, device/compiler metadata, memory footprint, and break-even
  size in machine-readable output and a reviewed evidence note.

### Step 5 / PR 5: Opt-in SLIMED adapter experiment

- Stage actual regular-face rows into the proven contiguous proof layout.
- Compare adapter outputs against the current CPU formula seam without
  replacing it.
- Produce a readiness recommendation covering correctness, performance,
  memory ownership, fallback, error handling, and remaining scatter/reduction
  risks.
- Do not enable default or production CUDA routing.

## Per-PR Review and Merge Gate

For every step:

1. Run the step's focused tests, dependency-free inventory tests, default
   non-CUDA build/tests, and `git diff --check`.
2. Push a focused branch and open a PR against `main`.
3. Send the PR to the dedicated CUDA PoC reviewer task.
4. Require a mergeability verdict covering scope, completeness, and
   compatibility/regression risk.
5. Resolve blocking findings in the same PR and rerun the review.
6. Ask the repository owner for explicit approval before merging.
7. Do not begin the next step until the current PR is merged or the owner
   explicitly changes the sequence.

The author and reviewer must not merge PRs. Existing non-CUDA behavior is the
control, and absence of CUDA must remain a supported configuration throughout
the series.
