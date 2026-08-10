# Persistent CUDA Mesh State, Geometry, And Regular Membrane Candidates

This document covers Steps 3 through 5 of the end-to-end CUDA residency program.
Step 3 added persistent storage and transaction control. Step 4 adds only the
eligible regular-face area/volume calculation and deterministic global
area/volume reductions. Step 5 adds the complete regular membrane formula into
candidate buffers. There is still no force scatter, evaluator routing, or host
`Mesh` publication.

## Authority and ownership

`CudaMeshState` owns one nonblocking CUDA stream and every buffer associated
with one packed regular mesh. CUDA types remain confined to the opt-in `.cu`
translation unit; ordinary builds discover the structured non-CUDA stub.
Accepted host state remains authoritative until later routing steps.

The persistent groups are topology/incidence, numerical plan, parameters,
accepted/previous/candidate coordinates, reference coordinates, candidate
geometry/status buffers, and membrane diagnostic/output buffers. Every
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
and the stream have been released. Facade-level stream cleanup debt overlays
the closed core report until repeated `close()` or `retry_cleanup()` destroys
the retained stream; rejected calls cannot erase that debt.

The allocation high-water mark for an update must fit the configured fraction
of current free device memory. The default is one half. Byte arithmetic and
capacity growth are checked before allocation.

## Transaction contract

The supported path is:

`IdleAccepted -> CandidatePrepared -> Computing -> Validated -> commit`

`compute_candidate_geometry()` owns the `Computing -> Validated` portion for
Step 4. It evaluates all packed non-ghost regular faces against the candidate
coordinate slot, then reduces full face-indexed area and legacy volume arrays
in ascending face-index order. Boundary faces remain physical and are
evaluated; ghost-face slots remain exact zero. The initial deterministic
reduction deliberately uses one device writer and no floating-point atomics.
Degenerate finite geometry is valid and produces zero area/volume rather than
being rejected.

The kernel uses the packed `[sample][row][local-control]` shape rows. For each
of the three samples it forms position and the two first derivatives, computes
their cross product, and preserves the production formula:

```text
area   += 0.5 * quadrature_coefficient * norm(cross(dV, dW))
volume += 0.16666666666 * quadrature_coefficient
          * position.x * cross(dV, dW).x
```

The second expression intentionally retains the existing legacy first-
component `dot_row` behavior. A device status rejects invalid indices or
nonfinite results before the candidate becomes validated.

`compute_candidate_membrane()` is an alternative candidate operation from
`CandidatePrepared`. It consumes all seven weighted rows and the packed
per-face spontaneous curvature plus global bending/area/volume parameters. It
emits, without scatter:

- per-sample surface measure, mean curvature, unit normal, and bending energy;
- per-face area, legacy volume, bending energy, integrated mean curvature, and
  normalized face normal; and
- 12 occurrences x 9 components ordered as bending xyz, area xyz, volume xyz.

The device formula follows `Mesh::element_energy_force_regular()` including
the current half-quadrature convention, dual-basis derivatives, bending
gradient matrices, and global constraint factors. A structured status records
the first invalid source, degenerate sample, nonfinite intermediate, or
nonfinite output together with evaluated-face and sample indices. Such a
candidate enters `Failed`; `recover()` returns to the unchanged accepted state.
Unlike Step 4 geometry, a zero surface measure is invalid for Step 5 because
the force formula requires its inverse. No source incidence plan is consumed
and no vertex-indexed force buffer is written.

Commit rotates candidate into accepted, accepted into previous, and the old
previous slot into reusable candidate storage while advancing the accepted
coordinate generation without a mesh-sized copy. Rollback from any live
candidate phase synchronizes, invalidates the candidate, and preserves the
accepted handle, bytes, generation, and slot. A compute/validation failure
enters `Failed`; explicit recovery synchronizes and returns to the unchanged
accepted state. Candidate preparation is currently an explicitly instrumented
host-to-device transfer. Step 9 replaces that operation inside resident line
searches; it is not hidden or misclassified here.

Each transfer records attempted/completed operation and byte counts under a
stable reason: topology, numerical plan, parameters, accepted coordinates,
reference coordinates, candidate coordinates, candidate geometry or membrane
storage, and geometry or membrane diagnostics. Steps 4 and 5 copy outputs to
the host only for their explicit comparison APIs and reports; those diagnostic
copies are classified and are not a production route. Allocation and
transaction epochs, live bytes, allocation/free counts, synchronizations,
roles, generations, and the last outcome are also reportable.
`lastDirtyGroups` is reset at the start of each candidate-upload decision. A
valid upload marks only `CandidateCoordinates`, retaining that mark after copy
or synchronization failure; rejection before an upload leaves every flag
clear.

## Evidence

The hardware-independent tests use the same state core with an injected memory
driver. They cover generation dirtiness, exact rollback, swap-on-commit,
illegal transitions, stale generations, memory-budget rejection, and injected
allocation, copy, and synchronization failures. The warmed loop proves no
allocation after initial residency and accounts for every repeated candidate
transfer. The reviewed amendment passes 22/22 focused tests, including
post-commit selective-update composition and retryable staging, replacement,
final-close release failures, stream-destroy retry, and candidate dirty-state
reporting. Step 4 adds natural, local-control permutation, sample-varying
curved, boundary, ghost, and degenerate geometry fixtures. It compares the
shared independent packed CPU oracle to every CUDA face/global result and
directly binds that same oracle to `Mesh::calculate_element_area_volume()` on a
curved production regular mesh at the `1.0e-12` gate. Injected kernel,
diagnostic-copy, and synchronization
failures and injected nonzero status, nonfinite face output, negative area, or
nonfinite totals remain recoverable without validating or changing accepted
state. Step 5 additionally rejects injected kernel, diagnostic-copy,
synchronization, status, nonfinite-force, and zero-surface failures while
preserving accepted bytes and recoverability. Its independent packed CPU
oracle is compared directly with the production regular formula at the
per-face and per-occurrence levels.

The explicit native proof builds and runs with:

```sh
python3 scripts/run_cuda_mesh_state_report.py \
  --require-cuda --iterations 20
```

The native report executes the natural, permuted, sample-varying curved,
boundary/ghost, degenerate, and production-formula CPU-oracle fixtures on the
actual CUDA kernels. Each case runs 20 geometry and 20 membrane candidate
transactions. Membrane evidence binds every sample diagnostic, face
observable, and 12x9 occurrence contribution; the degenerate case must report
the structured failure and recover on every repeat. The runner rejects a
report with any missing or false case field. The aggregate requires both
geometry and membrane maximum error at or below `1.0e-12` plus bitwise
repeatability. It also closes
explicitly before declaring success and requires `Closed`, zero cleanup debt,
zero final resident bytes, and exact allocation/free balance. Geometry parity,
repeatability, and teardown are therefore part of the RTX pass predicate, not
informational fields or destructor side effects after reporting. The recorded
RTX proof covers 240 transactions. Its membrane maximum absolute error is
`3.1086244689504383e-15`; geometry remains
`1.3877787807814457e-17`. It has no warmed allocations and exact allocation/
free balance.

The non-CUDA contract is independently runnable with `--stub`. Native evidence
for the development RTX machine is recorded in
`analysis/cuda_mesh_state_report_rtx4050.json`. No production or default build
depends on either report target.
