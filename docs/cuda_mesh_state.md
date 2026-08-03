# Persistent CUDA Mesh State And Transactions

This is Step 3 of the end-to-end CUDA residency program. It adds storage and
state control only: there are no force formulas, kernels, evaluator routing, or
host `Mesh` publication in this step.

## Authority and ownership

`CudaMeshState` owns one nonblocking CUDA stream and every buffer associated
with one packed regular mesh. CUDA types remain confined to the opt-in `.cu`
translation unit; ordinary builds discover the structured non-CUDA stub.
Accepted host state remains authoritative until later routing steps.

The persistent groups are topology/incidence, numerical plan, parameters,
accepted/previous/candidate coordinates, and reference coordinates. Every
group is keyed by the corresponding `MeshPackGenerations` value. Equal
generations cause no allocation, copy, or synchronization. A changed group is
allocated geometrically, copied into staging, synchronized, and installed only
after the whole requested update succeeds. Allocation or copy failure releases
staging and leaves resident generations and accepted coordinate storage exact.
A topology change requires fresh dependent generations.

Release failures retain their handles in an explicit cleanup-debt group. A
failed staging rollback returns `CleanupFailed` while leaving scientific state
unchanged. A replacement that has already published returns success and reports
`cleanupPending` plus `cleanupError`, so publication is never ambiguous; further
state-changing operations require `retry_cleanup()`. Final close enters
`Closing`, retains failed handles, and can be called again until every buffer
and the stream have been released.

The allocation high-water mark for an update must fit the configured fraction
of current free device memory. The default is one half. Byte arithmetic and
capacity growth are checked before allocation.

## Transaction contract

The supported path is:

`IdleAccepted -> CandidatePrepared -> Computing -> Validated -> commit`

Commit rotates candidate into accepted, accepted into previous, and the old
previous slot into reusable candidate storage while advancing the accepted
coordinate generation without a mesh-sized copy. Rollback from any live
candidate phase synchronizes, invalidates the candidate, and preserves the
accepted handle, bytes, generation, and slot. A compute/validation failure
enters `Failed`; explicit recovery synchronizes and returns to the unchanged
accepted state. Candidate preparation is currently an explicitly instrumented
host-to-device transfer. Step 9 replaces that operation inside resident line
searches; it is not hidden or misclassified here.

Each transfer records attempted/completed operation and byte counts under one
of six stable reasons: topology, numerical plan, parameters, accepted
coordinates, reference coordinates, or candidate coordinates. Allocation and
transaction epochs, live bytes, allocation/free counts, synchronizations,
roles, generations, and the last outcome are also reportable.

## Evidence

The hardware-independent tests use the same state core with an injected memory
driver. They cover generation dirtiness, exact rollback, swap-on-commit,
illegal transitions, stale generations, memory-budget rejection, and injected
allocation, copy, and synchronization failures. The warmed loop proves no
allocation after initial residency and accounts for every repeated candidate
transfer. The reviewed amendment passes 18/18 focused tests, including
post-commit selective-update composition and retryable staging, replacement,
and final-close release failures. The clean default suite passes 189/189 tests
when the independently reproduced baseline scaffold-force defect is excluded.

The explicit native proof builds and runs with:

```sh
python3 scripts/run_cuda_mesh_state_report.py \
  --require-cuda --iterations 20
```

The non-CUDA contract is independently runnable with `--stub`. Native evidence
for the development RTX machine is recorded in
`analysis/cuda_mesh_state_report_rtx4050.json`. No production or default build
depends on either report target.
