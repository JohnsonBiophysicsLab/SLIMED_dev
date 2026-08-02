# CUDA Regular-Face Residency Adapter Evidence

Date: 2026-08-02. Baseline: `origin/main` merge
`3a841f25f54472754e081830995cd03ed5ff2a4b` (PR #158).
Machine-readable evidence:
`analysis/cuda_regular_face_adapter_rtx4050.json`.

This is Step 5 of `docs/cuda_poc_implementation_plan.md`. It is an opt-in
adapter experiment and does not enable production CUDA routing, add a Makefile
target, change a production source/header, or make CUDA a default dependency.

## Outcome

Persistent device state can amortize transfer cost for the proven regular
weighted-sample seam. Transfer-inclusive CUDA first beat the eight-thread
OpenMP comparator at four resident iterations for both tested face batches:

- 4,096 faces: `1.168x` at four iterations, rising to `5.149x` at 64;
- 32,768 faces: `1.268x` at four iterations, rising to `4.752x` at 64.

One iteration did not beat OpenMP (`0.327x` and `0.466x`). This confirms the
Step 4 diagnosis: the GPU arithmetic is useful only when a larger pipeline
keeps changing simulation state on the device and avoids round trips.

The result is an upper bound, not a production integration case. The harness
uses a device-resident producer surrogate that applies deterministic local
updates before each forward/transpose pair. SLIMED does not yet have production
device ownership, a full GPU force formula, or a proven GPU scatter/reduction.
The project is therefore **not ready for production integration**.

## Adapter and correctness scope

The experiment stages the current second-order regular rows produced by
`Param::shapeFunctions` into the reviewed contiguous three-sample, seven-row,
12-control layout. The coordinate fixture uses the established regular-face
one-ring source order `9,15,10,16,22,11,17,23,29,18,24,30` on a regular
triangular lattice.

The CUDA adapter's forward and transpose outputs are compared with the
explicit-order serial and OpenMP weighted rows consumed by
`Mesh::element_energy_force_regular` after each complete resident sequence. Across all
eight cases, the maximum forward delta was `1.89e-15` and the maximum transpose
delta was `8.89e-15`, below the frozen `1.0e-12` gate.

The binary also links the current production sources and performs an isolated
dry run of `Mesh::element_energy_force_regular` on the same regular-face
coordinates and rows. It produced finite, nonzero bending/area/volume force
outputs (`max |force| = 3.3653`) and finite curvature/energy. This verifies the
real downstream CPU formula seam without replacing or rerouting it.

## Residency method

For each measured sequence:

1. production regular weights are copied once outside repeated timings;
2. controls and row gradients are copied to the device once;
3. a deterministic device-local state update surrogate and both weighted
   kernels run for 1, 4, 16, or 64 iterations;
4. only the final forward and transpose outputs are copied back.

Serial and OpenMP comparators perform the same state updates and operations.
Resetting comparator state happens outside the serial/OpenMP and CUDA
kernel-only intervals. The transfer-inclusive CUDA interval includes both
initial dynamic-input transfers, every resident update and weighted kernel,
final output transfers, and synchronization.

Each case used five warm-ups and 30 measured repetitions. Tables show median /
nearest-rank p95 milliseconds.

| Faces | Iterations | Serial CPU | 8-thread OpenMP | CUDA resident kernel | CUDA resident end-to-end | End-to-end / OpenMP |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4,096 | 1 | `1.307 / 1.359` | `0.329 / 0.370` | `0.111 / 0.122` | `1.007 / 1.108` | `0.327x` |
| 4,096 | 4 | `5.245 / 5.544` | `1.548 / 1.756` | `0.373 / 0.547` | `1.325 / 1.543` | `1.168x` |
| 4,096 | 16 | `23.834 / 31.790` | `7.189 / 9.627` | `1.404 / 1.452` | `2.553 / 2.891` | `2.816x` |
| 4,096 | 64 | `92.432 / 130.521` | `34.228 / 39.343` | `5.535 / 5.564` | `6.647 / 7.055` | `5.149x` |
| 32,768 | 1 | `12.921 / 21.119` | `3.521 / 4.761` | `0.799 / 0.819` | `7.554 / 9.162` | `0.466x` |
| 32,768 | 4 | `51.350 / 64.468` | `15.592 / 18.209` | `3.561 / 3.640` | `12.295 / 13.388` | `1.268x` |
| 32,768 | 16 | `206.200 / 227.836` | `60.665 / 68.742` | `12.213 / 12.785` | `19.419 / 20.584` | `3.124x` |
| 32,768 | 64 | `838.337 / 979.279` | `261.119 / 305.967` | `48.867 / 48.930` | `54.951 / 55.490` | `4.752x` |

## Readiness recommendation

### Correctness

The production rows, regular-face coordinate order, forward seam, transpose
seam, and isolated production CPU formula dry run pass. A full GPU force
formula has not been implemented or compared.

### Performance

Four or more resident iterations beat the measured OpenMP comparator, but the
device-resident producer is only a surrogate. This evidence cannot establish
speedup for a real SLIMED optimization/dynamics step until its actual upstream
and downstream operations remain resident.

### Memory ownership

All device buffers are proof-local RAII allocations. There is no production
owner, lifetime policy, invalidation rule, synchronization contract, or
multi-mesh/device policy.

### Fallback and error handling

Missing `nvcc` or a CUDA device remains an explicit machine-readable skip.
CUDA calls, buffer cardinalities, grid limits, and a 50%-of-free-memory budget
are checked. No production fallback path is changed because no production path
calls this adapter.

### Scatter and reduction

GPU force scatter, duplicate source-id aggregation, per-thread accumulation,
and deterministic global reduction remain unimplemented. The proven transpose
kernel is not a substitute for these production responsibilities.

### Decision

Stop the current CUDA PoC after this readiness report. Any further production
work requires a separately scoped and reviewed design for device ownership, an
end-to-end device-resident simulation pipeline, the complete force formula,
fallback/error policy, and deterministic scatter/reduction.

## Reproduce

```bash
python3 scripts/run_cuda_regular_face_adapter.py \
  --require-cuda \
  --batch-sizes 4096,32768 \
  --resident-iterations 1,4,16,64 \
  --warmups 5 --repetitions 30 --omp-threads 8
```

The run used the same RTX 4050 Laptop GPU, native `compute_89/sm_89`, CUDA
13.3, GCC 15.2, eight observed OpenMP threads, and WSL2 host described in the
machine-readable evidence. Host power mode and thermal/clock throttling remain
unavailable, so results must not be extrapolated beyond this machine and run.
