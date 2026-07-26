# Valence-4 Face-Loop Observable Shadow

This review-gated proof composes the approved closed valence-4 octahedron
topology/source representation, the backend-neutral source-keyed kernel helper,
and the existing `Mesh::element_energy_force_regular()` scientific algebra.
It is a standalone shadow, not a production face-loop route.

The harness validates the complete eight-face package before touching
caller-owned outputs. It then evaluates every face in serial and under actual
OpenMP teams of 1, 2, 3, 4, and 8 threads, with five repeats per team and
static scheduling. OpenMP accumulation uses production-shaped six-source by
nine-component force buffers and ascending-thread reduction.

The proof gates:

- per-face bending energy, mean curvature, canonical normal orientation, area,
  full signed volume, and legacy visible volume;
- global bending, area-constraint, volume-constraint, and total energy;
- all `fBend`, `fArea`, and `fVolume` source components;
- production-shaped six-vertex by nine-component force observables;
- exact eight-face collision coverage in every one of 54 force slots;
- an independent long-double nested source/kind/axis force oracle;
- an independent raw destination formula, `source * 9 + kind * 3 + axis`,
  which builds expected force and collision vectors without calling the
  candidate `force_index()` helper, followed by raw-slot comparison;
- an independent exact-layout sentinel that does not reuse the candidate
  flattening helper when it constructs or reads expected slots;
- explicit finite-value checks for every face scalar, normal component,
  per-face force component, flattened force slot, and global scalar before
  any maximum-delta reduction, plus a binding nonfinite negative regression;
- source permutation and duplicate-row invariance from the predecessor
  source-keyed proof;
- atomic rejection of a malformed row in the final face, proven against a
  fully seeded and complete `ShadowOutput` snapshot including every face
  observable and force, all 54 force/collision slots, all global fields,
  requested/actual team state, and proof route/one-ring state; and
- rejection of a flipped canonical normal oracle.

The OpenSubdiv-derived rows are generated only through the explicit
`OPENSUBDIV_ROOT` proof path. An absent dependency skips cleanly. Default
builds, tests, CI, and the readiness verifier remain OpenSubdiv-free.

The machine-readable boundary is explicit:

```text
proof_only: true
production_call_shadow: true
not_production_routing: true
production_route_enabled: false
actual_production_force_path_executed: false
production_face_loop_executed: false
production_one_rings_populated: false
```

Production `Face::oneRingVertices` remain empty before and after the proof.
The production face loop, force/scatter formulas, OpenMP scheduling and
reductions, checkpoint/output, propagation, optimizer, boundary behavior,
fixtures, and broader-valence routing are unchanged.

## Residual Boundary

This package establishes proof-only serial/OpenMP observable parity for the
approved valence-4 topology. A guarded production face-loop representation or
route remains a separate production C++ design and review decision. This proof
does not authorize one-ring population, production execution, or broader
valence support.
