# CUDA Canonical Mesh Pack And Eligibility Preflight

Date: 2026-08-02. Baseline: `origin/main` at
`8517119ddefb1e7ef5d45fdee6dbe145932d9f9d` (merge of PR #165).

This is Step 2 of
`docs/cuda_end_to_end_residency_force_scatter_implementation_plan.md`.
Production evaluator routing remains disabled. This package allocates no GPU
scientific buffer, launches no kernel, invokes no CUDA API, changes no `Mesh`,
and adds no automatic backend selection or per-face fallback.

## Canonical snapshot contract

`include/cuda/Cuda_mesh_pack.hpp` defines a backend-neutral owning snapshot.
The implementation reads the existing CPU `Mesh`, `Face`, `Vertex`, and
`Param` objects without mutating them. A successful pack has these fixed
orders:

- vertex arrays are indexed by declared contiguous zero-based vertex ID;
- face masks are indexed by declared contiguous zero-based face ID;
- evaluated non-ghost faces are in ascending declared face ID;
- oriented triangle vertices retain their existing local order;
- the 12 one-ring source IDs retain each face's existing local-control order;
- quadrature samples are `[sample][v,w,u]`;
- shape weights are `[sample][row][local-control]`; and
- coordinates are `[vertex ID][x,y,z]` for accepted, previous, and reference
  generations.

Container storage order is deliberately not part of the contract. The packer
first builds validated ID tables, so permuting the `vertices` or `faces`
vectors does not change a scientifically equivalent packed snapshot.
Duplicate or gapped declared IDs are rejected.

Every evaluated physical face must be a regular 12-control face. A repeated
source across different faces is expected and preserved. A repeated source
within one regular face is malformed and rejected with its face ID, local
control, and source ID. Ghost faces are not evaluated, but face boundary/ghost
masks are preserved for all declared faces. Vertex boundary/ghost masks are
preserved for all declared vertices.

The packed physical parameters are the current curvature, surface, volume,
regularization, spring, target/current area and volume, insertion/spontaneous
curvature, deformation coefficients, element target area, constraint scheme,
`usingRpi`, boundary grid dimensions, and boundary mode. The numerical plan
must be the current order-2,
three-sample plan with a `3x3` `VWU`, `3x1` coefficients, and three `7x12`
shape matrices. All coordinates, rows, coefficients, face curvature, and
packed scalar parameters must be finite.

The caller supplies generation values because the current `Mesh` class has no
central generation counter. An optional expected topology generation rejects
a stale request before the packer reads topology. Later state ownership must
advance these values when topology, the numerical plan, parameters, accepted
coordinates, or reference coordinates change; it must not infer freshness
from pointer identity.

Failure is atomic at this API boundary. `RegularMeshPackResult::pack` is
published only after all validation and incidence construction completes.
Stable error codes distinguish stale topology, overflow, invalid cardinality,
invalid index, duplicate local source, unsupported topology, invalid numerical
plan, and nonfinite input. The diagnostic also names the failed operation and,
when applicable, face/local/source identity.

## Deterministic source-incidence plan

Canonical occurrence `o` is

```text
o = evaluated_face_ordinal * 12 + local_control
```

The packer constructs compressed source incidence in two checked passes:

1. count occurrences for every source ID while traversing canonical
   face/local order;
2. exclusive-scan those counts into `sourceOffsets[nVertices + 1]`;
3. refill `sourceOccurrences[nOccurrences]` using per-source cursors; and
4. validate monotonic offsets, the exact terminal count, matching source IDs,
   and exactly-once coverage of every occurrence.

Because refill traverses canonical occurrence order, each source range is
already ordered by ascending face ID then local control. Step 6 can reduce
each range in that frozen order without atomics. Isolated vertices have equal
adjacent offsets and an empty range.

All cardinality additions and products use checked unsigned arithmetic before
allocation. Packed IDs are limited to signed 32-bit range, while offsets and
occurrences are unsigned 64-bit values.

## Eligibility matrix

`evaluate_cuda_eligibility()` has only `cpu` and `cuda` choices; there is no
`auto`. Choosing `cpu` always leaves the existing CPU route allowed and does
not require or construct a CUDA pack. Choosing `cuda` succeeds only when all
of these conditions are explicitly proven:

1. the caller records explicit user selection;
2. CUDA was compiled by the explicit opt-in target;
3. a compatible device is available;
4. driver/runtime compatibility is established;
5. required double precision is established;
6. required launch limits are established;
7. the device memory budget is available;
8. the complete canonical input pack validates as regular;
9. OpenSubdiv is not requested;
10. scaffolding harmonic-bond energy is disabled;
11. Gag scaffolding energy is disabled;
12. idealized protein lattice energy is disabled;
13. thermal and pure-Metropolis modes are disabled;
14. dynamic-mesh execution is disabled;
15. insertion semantics are absent;
16. the selected boundary mode has a focused proof flag; and
17. no prior unrecovered CUDA error exists.

The capability and proof flags are control-plane evidence inputs. Step 3 or a
later activation package must translate the Step-1 backend report, memory
estimate, and reviewed workflow mode into them. This step does not guess from
hardware names, environment variables, or build macros.

CUDA rejection is exhaustive rather than first-error-only. Issues are emitted
once in the stable matrix order above, each with an enum code, operation, and
message. Stale generation, invalid packed data, and unsupported regular
topology have distinct eligibility codes.
An explicitly requested CUDA route must fail loudly on any issue; no caller is
authorized by this package to silently run CPU or mix CPU/CUDA faces.

## Validation evidence

`tests/test_cuda_mesh_pack.cpp` supplies a deliberately non-canonical storage
fixture with shared sources, a permuted face-local one-ring, a boundary face,
a ghost face, a ghost/boundary vertex, and distinct accepted/previous/reference
coordinates. Its gates prove:

- exact integer and floating-point round-trip for topology, masks, numerical
  rows, quadrature, coordinates, face curvature, generations, and parameters;
- storage-permutation invariance;
- exact agreement with an independent grouped-tuple incidence oracle that
  does not call the production incidence builder;
- preservation of shared cross-face occurrences and ghost exclusion;
- atomic rejection of duplicate local sources, irregular cardinality,
  invalid IDs, stale topology, and nonfinite input;
- checked addition and multiplication overflow behavior;
- successful entry only for the complete explicit CUDA envelope;
- unconditional preservation of the explicit CPU route; and
- exact stable order and classification of simultaneous rejection reasons.

`scripts/inventory_cuda_mesh_pack_preflight.py` protects the source/API/doc
anchors, absence of CUDA calls and scientific device allocation, and absence
of a production evaluator/optimizer/dynamics route reference.

Validation on the Step-2 branch used isolated object directories so the
Makefile could not reuse OpenMP objects in a serial link:

- focused native pack/preflight suite: all 14 tests pass;
- focused Python Step-2, protected-plan, and legacy production-surface gates:
  all 20 tests pass;
- strict `-Wall -Wextra -Wpedantic -Werror` host compilation: pass;
- isolated default serial build: pass;
- isolated OpenMP build: pass;
- complete native suite: 169 of 170 pass; the sole failure is the documented
  pre-existing uninitialized expected-vector test
  `EnergyForceEvaluatorTest.SharedHelperRecordsScaffoldEnergyAndForceSideEffects`;
  and
- complete Python discovery: legacy historical-branch inventories reject the
  cumulative mainline/Step-2 changed-path set (43 failures, 32 intentional
  skips). The one content-based production-surface false positive exposed by
  that run was removed; its focused legacy guard now passes. Those historical
  exact-base inventories are not Step-2 acceptance gates.

The author and reviewer do not merge this step. Send the focused PR and exact
head to the dedicated CUDA production reviewer. Step 3 starts only after the
reviewer reports mergeability and the repository owner explicitly approves
the Step-2 merge.
