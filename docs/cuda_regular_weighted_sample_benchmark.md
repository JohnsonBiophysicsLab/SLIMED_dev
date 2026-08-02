# CUDA Regular Weighted-Sample Benchmark Evidence

Date: 2026-08-02.
Baseline: `origin/main` at merge commit
`12ebc9669c815bd117551194cf4fc1c99144654a` (PR #156).
Machine-readable evidence:
`analysis/cuda_regular_weighted_sample_benchmark_rtx4050.json`.

This is Step 4 of `docs/cuda_poc_implementation_plan.md`. It benchmarks the
proven forward-plus-transpose regular-row seam without changing a Make target,
production source, backend route, formula, scatter, or default behavior.

## Outcome

The GPU computation is substantially faster after data is resident, but host
transfer cost defeats the eight-thread OpenMP comparator at every tested batch.
At the largest case, batch 1,048,576:

- CUDA kernel-only median is `16.498 ms`, a `17.07x` speedup over serial CPU and
  `5.03x` over eight-thread OpenMP;
- transfer-inclusive CUDA median is `188.947 ms`, a `1.49x` speedup over serial
  CPU but only `0.439x` the performance of OpenMP; and
- host-to-device plus device-to-host medians total about `175.30 ms`, explaining
  most of the end-to-end result.

Transfer-inclusive CUDA first beats serial CPU at batch 4,096. No
transfer-inclusive break-even against OpenMP was observed through batch
1,048,576. Therefore this evidence does not support production CUDA integration.
Step 5 may test only whether an opt-in adapter can keep data resident or
otherwise amortize transfers; kernel-only speedup is not an integration case.

## Compared workload

Every timed invocation performs both proven operations for the same batch:

```text
forward = W * controls
transpose = W^T * rowGradient
```

The production `N=2` weights are constant and copied to the GPU once, matching
the expected reuse of regular shape rows. Transfer-inclusive timing includes
both dynamic inputs (`controls`, `rowGradient`), both outputs, both kernels,
and synchronization. It excludes only the one-time constant-weight setup.

Before timing each batch, serial CPU, OpenMP CPU, and CUDA outputs must be
finite and agree within the frozen `1.0e-12` absolute tolerance. The maximum
observed forward and transpose CPU-CUDA deltas were
`3.552713678800501e-15` and `5.329070518200751e-15`.

## Method

The measurement session used batch sizes
`1, 16, 256, 4096, 32768, 131072, 524288, 1048576`. The upper-bound case was
run immediately after the initial seven-case sweep under the same unchanged
configuration. Each metric used five warm-ups and 30 measured repetitions.
Tables report median and nearest-rank p95 in milliseconds. Serial CPU, OpenMP,
transfers, and end-to-end CUDA use a monotonic host clock; kernel-only CUDA uses
CUDA events.

The OpenMP comparator requested and observed eight threads through `libgomp`,
with `OMP_DYNAMIC=FALSE`, static scheduling, `OMP_PLACES=cores`, and
`OMP_PROC_BIND=TRUE`. Serial and OpenMP functions use identical per-output
arithmetic; OpenMP partitions independent batch items and performs no shared
floating-point reduction.

The largest case required 1,660,946,400 device bytes, 25.80% of the 6 GiB device.
The harness rejects any case exceeding 50% of free device memory before the
sweep, leaving explicit capacity headroom while retaining the required 30-run
CPU comparators.

## Timing evidence

Each cell is `median / p95` milliseconds.

| Batch | Serial CPU | OpenMP CPU | CUDA kernel | Host to device | Device to host | CUDA end-to-end |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `0.000402 / 0.000431` | `0.001307 / 0.001399` | `0.028272 / 0.073920` | `0.067820 / 0.100776` | `0.071586 / 0.106660` | `0.157680 / 0.317300` |
| 16 | `0.004096 / 0.004114` | `0.002355 / 0.027957` | `0.032128 / 0.056096` | `0.062373 / 0.097667` | `0.064453 / 0.194557` | `0.161715 / 0.313683` |
| 256 | `0.093629 / 0.102439` | `0.017145 / 0.095657` | `0.026432 / 0.056320` | `0.098949 / 0.215143` | `0.211775 / 0.288985` | `0.321921 / 0.459317` |
| 4,096 | `1.381009 / 2.091371` | `0.275875 / 1.484119` | `0.080240 / 0.121856` | `0.447665 / 0.534980` | `0.522724 / 0.665085` | `1.178055 / 1.480145` |
| 32,768 | `9.549325 / 12.405750` | `2.682786 / 4.780932` | `0.560128 / 0.586432` | `3.764664 / 5.975711` | `2.935957 / 3.280935` | `6.603360 / 8.343034` |
| 131,072 | `37.984370 / 50.506346` | `11.272698 / 14.592216` | `2.204672 / 2.212864` | `12.197110 / 14.182072` | `13.376927 / 16.491113` | `27.551702 / 35.374842` |
| 524,288 | `150.217527 / 184.397264` | `48.879301 / 54.663840` | `8.653312 / 8.802304` | `46.671213 / 55.345372` | `44.448157 / 51.481037` | `105.968515 / 116.066474` |
| 1,048,576 | `281.534939 / 325.107360` | `83.025066 / 96.360988` | `16.497583 / 17.539776` | `82.759024 / 95.319548` | `92.536895 / 105.506945` | `188.947106 / 210.151219` |

## Speedup evidence

| Batch | Kernel / serial | Kernel / OpenMP | End-to-end / serial | End-to-end / OpenMP |
| ---: | ---: | ---: | ---: | ---: |
| 1 | `0.014x` | `0.046x` | `0.003x` | `0.008x` |
| 16 | `0.127x` | `0.073x` | `0.025x` | `0.015x` |
| 256 | `3.542x` | `0.649x` | `0.291x` | `0.053x` |
| 4,096 | `17.211x` | `3.438x` | `1.172x` | `0.234x` |
| 32,768 | `17.048x` | `4.790x` | `1.446x` | `0.406x` |
| 131,072 | `17.229x` | `5.113x` | `1.379x` | `0.409x` |
| 524,288 | `17.360x` | `5.649x` | `1.418x` | `0.461x` |
| 1,048,576 | `17.065x` | `5.033x` | `1.490x` | `0.439x` |

## Environment and limits

The run used an NVIDIA GeForce RTX 4050 Laptop GPU, compute capability 8.9,
CUDA 13.3 (`nvcc` 13.3.73), driver API 13.0, runtime API 13.3, GCC 15.2.0,
and a 13th Gen Intel Core i5-13450HX with eight physical and 16 logical cores
under WSL2. Native `compute_89/sm_89`, `-O3`, C++17, and `-fopenmp` flags are
recorded in the JSON evidence.

Windows host power mode, AC/battery state, GPU power state, and thermal/clock
throttling telemetry were unavailable through this WSL setup. The sweep ran
sequentially under one unchanged host configuration, but the missing telemetry
limits conclusions to this observed machine/run and prevents claims about
power-normalized or throttle-free performance. Results must not be extrapolated
to other CPUs, thread counts, affinity, GPUs, drivers, transfer paths, precision,
or production data ownership.

## Reproduce

```bash
python3 scripts/run_cuda_regular_weighted_sample_benchmark.py \
  --require-cuda --warmups 5 --repetitions 30 --omp-threads 8
```

Without `nvcc` or a usable CUDA device, the default runner emits an explicit
machine-readable successful skip. CUDA is not discovered or invoked by any
default Make target.

## Validation record

- The focused CUDA/plan suite passed 38/38 tests.
- Python byte-compilation and committed JSON parsing passed.
- The native correctness and timing sweep passed at every recorded batch.
- `make test` completed without invoking CUDA, and all 144 unaffected C++
  tests passed; the established baseline-only uninitialized expected-vector
  test remains unrelated.
- The complete staged diff passed `git diff --check`.
- The reviewer-supplied oversized batch `10248191152060862009` is rejected by
  the Python runner before build and independently by the compiled C++ parser
  before allocation (`batch size exceeds OpenMP loop range`). Checked
  multiplication/addition protects buffer cardinalities, byte counts, grid
  rounding, and the device-memory safety calculation.
