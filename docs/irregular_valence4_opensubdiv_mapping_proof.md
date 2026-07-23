# Valence-4 OpenSubdiv Mapping/Sample/Transpose Proof

The canonical closed regular octahedron serialized under
`data/fixtures/candidates/closed_valence4_octahedron` is approved narrowly as
a stand-in for this mechanical proof lane:

```text
approved_fixture: true
approved_for_mapping_sample_transpose_proof: true
approved_scope: mechanical OpenSubdiv Ptex identity, sample ordering, source-row mapping, and linear transpose evidence
scientifically_approved: false
proof_only: true
not_production_routing: true
production_route_enabled: false
```

The generic scientific flag remains false because this approval does not
validate membrane geometry or force physics. The PR114 fail-loud production
guard remains the current behavior for every face in this fixture.

## Frozen Proof Plan

The opt-in report loads the six vertices and eight outward-oriented face rows
directly from the fixture CSV files. For Loop triangles, fixture face row `i`
must map to OpenSubdiv/Ptex face `i`, for exact IDs `0..7`, and every sample
must have a successful `PatchMap` lookup whose patch parameter face ID is the
same ID.

Every face uses these samples in the displayed order:

| sample | `v` | `w` | `u` | OpenSubdiv | weight | formula factor |
| ---: | ---: | ---: | ---: | --- | ---: | ---: |
| 0 | `1/6` | `1/6` | `4/6` | `s=v,t=w` | `1/3` | `1/6` |
| 1 | `1/6` | `4/6` | `1/6` | `s=v,t=w` | `1/3` | `1/6` |
| 2 | `4/6` | `1/6` | `1/6` | `s=v,t=w` | `1/3` | `1/6` |

Ordering is face-major, then sample-major, yielding 24 samples. Each sample
emits dense rows keyed by original fixture IDs `0..5` in the fixed order
`value,du,dv,duu,dvv,duv,duv`. The mixed rows must be identical.

The report requires finite coefficients, value-row sum `1`, derivative-row
sums `0`, and patch-basis-expanded versus limit-stencil agreement within
`5e-6`. Duplicate entries are injected into every row, reversed, and
aggregated by ascending original source ID; the result must remain identical.
Per-face and global coverage unions must include all six IDs. This is an
aggregate coverage statement, not a claim that every individual row has
nonzero support on every ID.

The transpose diagnostic uses asymmetric source/axis scalar controls,
face/sample/row/axis-dependent gradients, and the frozen `1/3` sample weights.
Every sample and the stacked 24-sample map must satisfy
`g dot (W p) == (W^T g) dot p` within `1e-12 * scale`. Back-projection must
contain exactly 18 components and support all six original source IDs. The
wrapper runs the probe binary twice and requires byte-identical canonical
proof JSON; install paths remain outside that canonical JSON.

## Run

Dependency-absent behavior is an explicit skip:

```bash
scripts/run_irregular_valence4_opensubdiv_mapping_proof.sh --json
```

Present-dependency proof:

```bash
OPENSUBDIV_ROOT=/tmp/slimed-opensubdiv-install \
OPENSUBDIV_CXXFLAGS='-arch arm64' \
scripts/run_irregular_valence4_opensubdiv_mapping_proof.sh \
  --json --require-opensubdiv
```

Review inventory:

```bash
python3 scripts/inventory_irregular_valence4_mapping_proof.py --check
```

## Claim Boundary

This lane proves only mechanical mapping, samples, source-keyed derivative
rows, deterministic aggregation, coverage unions, and a linear transpose
identity for the approved stand-in. It does not prove production geometry,
production fBend/fArea/fVolume, scatter/OpenMP parity, broader-valence route
readiness, or any production fallback. No production route is enabled.
