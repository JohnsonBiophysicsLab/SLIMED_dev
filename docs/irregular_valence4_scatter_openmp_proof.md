# Valence-4 Scatter and Simulated OpenMP Shape Proof

This lane extends the approved proof-only valence-4 OpenSubdiv force-formula
evidence from PR #117. It remains:

- `proof_only: true`
- `scatter_openmp_shape_proof_only: true`
- `not_production_routing: true`
- `production_route_enabled: false`
- `scientifically_approved: false`

Run it explicitly with:

```bash
OPENSUBDIV_ROOT=/tmp/slimed-opensubdiv-install \
OPENSUBDIV_CXXFLAGS='-arch arm64' \
scripts/run_irregular_valence4_opensubdiv_scatter_openmp_proof.sh \
  --json --require-opensubdiv
```

Without `OPENSUBDIV_ROOT`, the wrapper exits successfully with `status:
skipped`. The default build and test dependency policy is unchanged.

## Evidence

The proof retains the 8 face-local contributions produced by the frozen
24-sample force-formula plan. Each face contribution is keyed by the original
fixture source IDs `0..5`.

For every face, the proof scatters the three force rows into the reviewed
nine-component source buffer layout:

```text
source_id * 9 + [fBend.x, fBend.y, fBend.z,
                 fArea.x, fArea.y, fArea.z,
                 fVolume.x, fVolume.y, fVolume.z]
```

All eight faces contribute to shared source slots, so the check exercises
multi-face collision accumulation on all six source IDs. The serial buffer is
compared against the direct source-keyed force result from PR #117. The direct
54-component expected buffer is packed without calling the scatter helper.

An additional exact-index oracle fills `fBend`, `fArea`, and `fVolume` with
distinct integer sentinels for every source and axis, invokes the scatter
helper once, and checks every destination slot independently. This prevents a
shared source/component-offset mistake from false-passing the numerical
regrouping comparisons.

The proof also requires all eight allocated face buffers to be finite and to
contain at least one force component above the fixed `1e-12` threshold.
Allocated-but-empty face slots therefore cannot satisfy the face-participation
claim.

The same eight contributions are assigned deterministically to three
proof-local thread buffers. Reduction proceeds in source, force-component,
then ascending thread-index order, matching the shape of the reviewed
production reduction. The serial and simulated-OpenMP buffers must agree under
an absolute `1e-12` tolerance. Split/reversed duplicate stencil aggregation
must produce the same final scatter buffer.

The current proof measured:

- direct source-force versus face-scattered buffer:
  `2.1094237467877974e-14`;
- serial versus simulated-OpenMP reduction:
  `2.1316282072803006e-14`;
- direct versus split/reversed-duplicate scatter: `0`.

## Boundaries

This is a production-*shape* proof, not production execution:

- The production topology setup still leaves this unsupported fixture's
  `Face::oneRingVertices` empty and rejects it before mutation.
- The proof uses a synthetic six-source identity list per face; it does not
  claim actual production `Face::oneRingVertices` population or scatter.
- It simulates production-shaped thread-local buffers and deterministic
  reduction. It does not invoke an OpenMP runtime or compare serial/OpenMP
  executables.
- It does not change routing, formulas, scatter code, OpenMP scheduling or
  reductions, dependency policy, output, checkpoints, propagation, or fixture
  files.

The follow-up proof in
`docs/irregular_valence4_production_openmp_shadow.md` now loads the approved
fixture through production `Mesh` setup, confirms that valence-4 production
one-rings remain empty, and exercises the proposed source mapping through a
real OpenMP runtime. It is still a proof-local production-call shadow, not a
production route. Actual broader-valence production routing remains
unapproved.
