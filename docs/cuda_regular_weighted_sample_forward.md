# CUDA Regular Weighted-Sample Forward Proof

Date: 2026-08-01.
Baseline: `origin/main` at merge commit
`06f10b028321a086c9890d9bc626e37031ce5ff0` (PR #154).

This is Step 2 of `docs/cuda_poc_implementation_plan.md`. It is a standalone,
opt-in correctness proof for the regular-face forward product `W * p`. It does
not change a Make target, production source, backend selection, scientific
formula, force scatter, or runtime behavior. CUDA remains optional.

## Proven seam

The experiment obtains the current production rows by calling
`get_gauss_quadrature_weight_VWU(2, ...)` and
`get_shapefunction_vector(...)`. It validates and flattens the resulting three
samples, seven rows, and 12 controls, then evaluates three coordinate axes for
every batch item:

```text
weighted[b,q,r,c] = sum(j=0..11) weights[q,r,j] * controls[b,j,c]
```

The serial CPU reference and CUDA kernel both accumulate controls in ascending
`j` order using `double`. Each CUDA thread owns one output component, so the
kernel has no floating-point atomics. Inputs and both outputs must be finite.
The fixed acceptance gate is a maximum absolute CPU-CUDA delta of `1.0e-12`;
the relative delta is diagnostic only.

The deterministic fixture uses an integer formula and no random-number
generator. The proof also rejects nonpositive/overflowing batch cardinalities,
production row-shape drift, CUDA allocation/copy/launch failures, and
nonfinite values with explicit diagnostics.

## Run it

The runner compiles into a temporary directory and does not invoke `make`:

```bash
python3 scripts/run_cuda_regular_weighted_sample_forward.py --require-cuda --batch-size 257
```

On hosts without `nvcc`, the default invocation emits a machine-readable
`skipped` result and succeeds because this is an optional experiment.
`--require-cuda` instead returns exit code 77. A compiled proof with no usable
device follows the same policy.

For the audited RTX 4050 Laptop GPU, the runner emits native Ada code with
`-arch=compute_89 -code=sm_89`. Alternate architecture flags are explicit
runner options and must describe the device being tested.

## Observed correctness evidence

The commands below ran in WSL2 Ubuntu on 2026-08-01 using CUDA 13.3
(`nvcc` 13.3.73), driver API 13.0, runtime API 13.3, and an NVIDIA GeForce RTX
4050 Laptop GPU with compute capability 8.9. The host CPU was a 13th Gen Intel
Core i5-13450HX with eight physical and 16 logical cores. GPU power state,
Windows host power mode, and AC/battery state were unavailable to this WSL
correctness runner and were recorded as unavailable rather than inferred.

| Batch | Components | Maximum absolute delta | Maximum relative delta (diagnostic) | Result |
| ---: | ---: | ---: | ---: | :--- |
| 1 | 63 | `1.7763568394002505e-15` | `8.881784197001252e-16` | passed |
| 257 | 16,191 | `3.552713678800501e-15` | `1.7763568394002505e-15` | passed |
| 4,097 | 258,111 | `3.552713678800501e-15` | `1.7763568394002505e-15` | passed |

The single-item case and the two non-block-aligned cases exercise the kernel's
partial-block boundary. All reported components were finite and all absolute
deltas were more than two orders of magnitude below the frozen tolerance.

This evidence proves only the forward operation on the stated machine and
fixture. The transpose, adjoint identity, control-order permutation, repeated
bitwise determinism, comparative timing, adapter, and production routing remain
future gated steps.

## Validation record

The focused dependency-free gate passed 15 tests:

```bash
python3 -m unittest \
  tests/test_cuda_regular_weighted_sample_forward.py \
  tests/test_cuda_poc_plan_inventory.py
python3 -m py_compile \
  scripts/run_cuda_regular_weighted_sample_forward.py \
  tests/test_cuda_regular_weighted_sample_forward.py
```

`make test -B` completed the forced default non-CUDA build. Running
`./bin/test_main --gtest_brief=1` reproduced the inherited baseline: 144 of
145 tests passed, and only
`EnergyForceEvaluatorTest.SharedHelperRecordsScaffoldEnergyAndForceSideEffects`
failed. Its expected force component is uninitialized; PR #154's independent
review reproduced the same baseline failure before this CUDA source existed.
This proof does not modify that test or its production path.
