# CUDA Backend Shell And Capability Report

Date: 2026-08-02. Baseline: `origin/main` at
`0b2b6dd425cb47e703c02dce0d32f89e23721b0d` (merge of PR #164).

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

The internal lifetime state machine remembers whether the retained context is
already pushed. A failed creation-time pop is retried without pushing the same
context twice. Cleanup never releases the shared primary-context reference
while its context may still be current or while a stream remains owned.
`DeviceContext::close()` reports cleanup failures; failed resources stay marked
live so a later explicit close or destructor can retry without double destroy
or double release.

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

Default serial, OpenMP, dynamics, test, and syntax targets compile the shared
error-name implementation and `src/cuda/Cuda_backend_stub.cpp`. They never
compile the `.cu` implementation. The stub never includes CUDA headers, links
a CUDA library, probes a driver, or creates a device context. It reports
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

The report executable explicitly closes each probe context and counts an
iteration only after stream destruction, preceding-context restoration, and
primary-context release all succeed. Ownership flags record the resources that
were successfully owned during that completed lifecycle. `query_backend()`
also closes its temporary context and converts cleanup failure into structured
unavailability.

## Native evidence

On the RTX 4050 Laptop GPU development machine, native `compute_89/sm_89`
construction succeeded for 20 consecutive RAII lifetime cycles. The report
is committed as `analysis/cuda_backend_report_rtx4050.json`. Its provenance
records base `0b2b6dd425cb47e703c02dce0d32f89e23721b0d` and tested implementation
commit `07d3aaebb0a714ed8be46a0bd78d306308cf720a`. It observed:

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
- injected driver-call tests for preceding-context restoration, failed pop,
  failed cleanup push, failed stream destruction, retry, and exactly-once
  primary-context release;
- Python tests/inventory for optional-target isolation, CUDA-free public
  headers, no kernel/scientific allocation, runner skip behavior, and route
  absence;
- native available, invalid-ordinal, and repeated lifetime reports;
- default serial/OpenMP/test compatibility; and
- base-to-head whitespace and scope checks.

Send the focused PR and exact head to the dedicated CUDA production reviewer.
The author and reviewer do not merge. Step 2 starts only after reviewer
mergeability and explicit repository-owner approval of the Step-1 merge.
