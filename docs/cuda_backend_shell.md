# CUDA Backend Shell And Capability Report

Date: 2026-08-02. Baseline: `origin/main` at
`a25a13906a314a40f5442f6068a3bde8bd0e8142` (merge of PR #163).

This is Step 1 of
`docs/cuda_end_to_end_residency_force_scatter_implementation_plan.md`.
Production evaluator routing remains disabled. No scientific device buffer is
allocated, no CUDA kernel exists in this slice, and no optimizer, dynamics,
force, energy, topology, checkpoint, or output behavior changes.

## Interface and ownership

`include/cuda/Cuda_backend.hpp` is the backend-neutral API. It exposes only
standard C++ types, a stable structured error enum, device capabilities, a
move-only `DeviceContext`, and creation/query results. CUDA headers and handle
types remain private to `src/cuda/Cuda_backend.cu`.

The CUDA implementation owns:

- one retained reference to the selected device's primary CUDA context;
- one `CU_STREAM_NON_BLOCKING` stream created while that context is current;
- balanced context push/pop operations during creation and destruction; and
- deterministic release of the stream followed by the retained context
  reference through RAII.

It does not call `cuDevicePrimaryCtxReset` or `cudaDeviceReset`, because the
primary context is process-shared with CUDA Runtime users. NVIDIA documents
that a retained primary context must be released and that it is shared with the
Runtime API:

- <https://docs.nvidia.com/cuda/cuda-driver-api/group__CUDA__PRIMARY__CTX.html>
- <https://docs.nvidia.com/cuda/cuda-driver-api/driver-vs-runtime-api.html>

The stream is explicitly nonblocking with respect to the legacy null stream,
as documented by NVIDIA:

- <https://docs.nvidia.com/cuda/cuda-driver-api/group__CUDA__STREAM.html>

## Structured report

The report records:

- compile-time and runtime availability;
- requested ordinal and device count;
- device name and compute capability;
- CUDA driver and Runtime API versions;
- total and current free device memory;
- multiprocessor, warp, maximum-thread, and asynchronous-engine counts;
- stream-ordered memory-pool support;
- retained-primary-context and nonblocking-stream ownership; and
- stable error code, operation, native code, and message.

Stable error codes distinguish not-compiled, no-device, insufficient-driver,
invalid-ordinal, initialization, capability-query, context-creation,
stream-creation, and context-stack failures. Missing CUDA is an explicit exit
`77` from the native report. The Python runner converts missing compiler/device
to a successful structured skip unless `--require-cuda` is used.

## Build boundaries

Default serial, OpenMP, dynamics, test, and syntax targets compile only
`src/cuda/Cuda_backend_stub.cpp`. The stub never includes CUDA headers, links a
CUDA library, probes a driver, or creates a device context. It reports
`not_compiled` without partial state.

CUDA discovery and compilation occur only after explicitly requesting:

```console
make cuda_backend_report \
  CUDA_NVCC=/usr/local/cuda/bin/nvcc \
  CUDA_HOST_CXX=/usr/bin/g++ \
  CUDA_COMPUTE_ARCH=compute_89 CUDA_SM_CODE=sm_89
```

Both standalone report targets are independent of the simulation's GSL
dependency. Ordinary and mixed simulation builds retain the existing GSL
requirement.

The non-CUDA executable seam can be inspected explicitly with:

```console
make cuda_backend_stub_report
./bin/cuda_backend_stub_report
```

The supported runner is:

```console
python3 scripts/run_cuda_backend_report.py \
  --require-cuda --lifecycle-iterations 20
```

The report executable destroys each completed probe context before starting
the next lifecycle iteration, then keeps the final successful context alive
through JSON emission. Thus its ownership flags describe live RAII ownership
at the reporting boundary. `query_backend()` instead creates and destroys a
temporary context; the same flags there record that the retain/create probe
succeeded, not ownership that outlives the call.

## Native evidence

On the RTX 4050 Laptop GPU development machine, native `compute_89/sm_89`
construction succeeded for 20 consecutive RAII lifetime cycles. The report
is committed as `analysis/cuda_backend_report_rtx4050.json` and observed:

- device count `1` and compute capability `8.9`;
- driver API `13000` and Runtime API `13030`;
- total device memory `6438780928` bytes;
- 20 multiprocessors, warp size 32, and 1024 maximum threads per block;
- one asynchronous engine and stream-ordered memory-pool support; and
- retained primary context and owned nonblocking stream both true.

Current free memory is intentionally reported at runtime rather than frozen as
an acceptance value.

## Validation and review boundary

The Step-1 gate includes:

- C++ tests for the default stub, stable errors, no partial context, and
  move-only ownership;
- Python tests/inventory for optional-target isolation, CUDA-free public
  headers, no kernel/scientific allocation, runner skip behavior, and route
  absence;
- native available, invalid-ordinal, and repeated lifetime reports;
- default serial/OpenMP/test compatibility; and
- base-to-head whitespace and scope checks.

Send the focused PR and exact head to the dedicated CUDA production reviewer.
The author and reviewer do not merge. Step 2 starts only after reviewer
mergeability and explicit repository-owner approval of the Step-1 merge.
