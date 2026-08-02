# CUDA Regular Weighted-Sample Transpose Proof

Date: 2026-08-02.
Baseline: `origin/main` at merge commit
`e5193a22c23ae65b99f8d0575b18492737557b90` (PR #155).

This is Step 3 of `docs/cuda_poc_implementation_plan.md`. It is a standalone,
opt-in correctness proof for the regular-face transpose product `W^T * g` and
its relationship to the Step 2 forward product. It does not alter a Make
target, production source, backend selection, scientific formula, force
scatter, or runtime behavior. CUDA remains optional and production routing
remains disabled.

## Proven operations

The experiment obtains the current production rows through
`get_gauss_quadrature_weight_VWU(2, ...)` and
`get_shapefunction_vector(...)`. It validates the frozen three-sample,
seven-row, 12-control shape and evaluates three `double` components:

```text
weighted[b,q,r,c] = sum(j=0..11) weights[q,r,j] * controls[b,j,c]

controlGradient[b,j,c] =
    sum(q=0..2) sum(r=0..6) weights[q,r,j] * rowGradient[b,q,r,c]
```

Each CUDA output component has exactly one writer. The transpose kernel uses no
floating-point atomics and performs its `q,r` sums in an explicit order. The
CPU reference uses the same stated mathematical order but separate host loops.
Forward and transpose CPU-CUDA comparisons each use the unchanged maximum
absolute gate of `1.0e-12`; relative deltas are diagnostic only.

## Independent gates

The host computes both sides of the adjoint identity with `long double`:

```text
left = dot(g, W * p)
right = dot(W^T * g, p)
residual = abs(left - right) / max(1, abs(left), abs(right))
```

CPU-reference and CUDA outputs pass that `1.0e-12` residual gate
independently. A deliberately nontrivial control permutation
`[5,0,11,3,8,1,10,6,2,9,4,7]` is applied consistently to weight columns and
control rows. The proof checks forward invariance and maps the permuted
transpose back to the natural control identity. Duplicate source-id
aggregation stays outside the device kernel as a host mapping contract.

Natural and permuted CUDA cases each execute 20 identical repetitions. Both
forward and transpose buffers must be byte-for-byte identical to their first
repetition. Every fixture and output component must be finite.

A hand-computed sparse sentinel sets literal flattened offsets `weight[251] =
2`, `control[35] = 3`, and `rowGradient[62] = 5`. CPU and CUDA must produce
only `forward[62] = 6` and `transpose[35] = 10`. This independently catches a
shared flattening error before the production fixture runs.

## Run it

```bash
python3 scripts/run_cuda_regular_weighted_sample_transpose.py \
  --require-cuda --batch-size 257
```

The runner builds in a temporary directory with native Ada flags
`-arch=compute_89 -code=sm_89` and explicitly selects `/usr/bin/g++` through
`-ccbin`. It never invokes `make`. When `nvcc` or a usable device is absent,
the default invocation emits a machine-readable successful `skipped` report;
`--require-cuda` returns exit 77 instead.

## Observed correctness evidence

The audited run used an NVIDIA GeForce RTX 4050 Laptop GPU (compute capability
8.9), CUDA 13.3 (`nvcc` 13.3.73), driver API 13.0, runtime API 13.3, and GCC
15.2.0 under WSL2 Ubuntu. Compiler flags, full command, host CPU topology,
OpenMP non-use, unavailable power fields, and WSL kernel are present in the
machine-readable report.

For batch 257:

| Gate | Observed value | Limit/result |
| --- | ---: | ---: |
| Forward CPU-CUDA maximum absolute delta | `3.552713678800501e-15` | `<= 1e-12` |
| Transpose CPU-CUDA maximum absolute delta | `5.329070518200751e-15` | `<= 1e-12` |
| Maximum CPU adjoint residual | `1.7615589872631764e-16` | `<= 1e-12` |
| Maximum CUDA adjoint residual | `5.834975514635307e-17` | `<= 1e-12` |
| Natural/permuted forward delta | `3.552713678800501e-15` | `<= 1e-12` |
| Natural/permuted transpose mapped delta | `0` | `<= 1e-12` |
| Natural bitwise repetitions | `20/20` identical | passed |
| Permuted bitwise repetitions | `20/20` identical | passed |
| Sparse flattened-index sentinel | exact | passed |

All inputs and outputs were finite. These values establish correctness only;
they are not performance evidence. Timing, transfer accounting, break-even
analysis, adapter staging, scatter, and production CUDA routing remain later
gated steps.

The same gates also passed at batch 1 and the non-block-aligned batch 4,097:

| Batch | Forward max abs | Transpose max abs | CPU adjoint max | CUDA adjoint max | Determinism |
| ---: | ---: | ---: | ---: | ---: | :--- |
| 1 | `3.552713678800501e-15` | `1.7763568394002505e-15` | `5.405403439998225e-17` | `3.3530844868438186e-17` | natural/permuted passed |
| 4,097 | `3.552713678800501e-15` | `5.329070518200751e-15` | `7.451043745494437e-17` | `6.579752339771297e-17` | natural/permuted passed |

## Validation record

The dependency-free focused gate passed 26 tests:

```bash
python3 -m unittest \
  tests/test_cuda_regular_weighted_sample_transpose.py \
  tests/test_cuda_regular_weighted_sample_forward.py \
  tests/test_cuda_poc_plan_inventory.py
python3 -m py_compile \
  scripts/run_cuda_regular_weighted_sample_transpose.py \
  tests/test_cuda_regular_weighted_sample_transpose.py
```

`make test` completed without invoking CUDA. Running all C++ tests except the
established baseline-only
`EnergyForceEvaluatorTest.SharedHelperRecordsScaffoldEnergyAndForceSideEffects`
case passed 144/144. This PR does not modify any Make/C++ input, and the sole
excluded test remains the pre-existing uninitialized expected-vector failure
documented and independently reproduced during the prior PR reviews.
