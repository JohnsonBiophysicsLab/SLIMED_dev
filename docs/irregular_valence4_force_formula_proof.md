# Valence-4 OpenSubdiv Force-Formula Proof

This approved lane extends the PR116 serialized octahedron
mapping/sample/transpose evidence only far enough to test proof-local regular
force algebra:

```text
approved_for_mapping_sample_transpose_proof: true
proof_only: true
force_formula_proof_only: true
not_production_routing: true
production_route_enabled: false
scientifically_approved: false
```

It is not physics validation. It does not establish production geometry or
output parity, `Face::oneRingVertices` scatter, serial/OpenMP parity, route
readiness, broader-valence routing, or scientific equivalence beyond this
proof.

## Formula Bridge

Before running valence-4 evidence, the wrapper runs the existing experimental
regular C++ adapter proof. That proof calls
`Mesh::element_energy_force_regular` with proof-local OpenSubdiv rows and
compares it with the reviewed local formula transcription. The present
validation measured maximum force-row difference
`1.7763568394e-15` and maximum scalar difference
`1.08420217249e-19`.

The valence-4 harness then mechanically uses the same reviewed bending, area,
and volume sample algebra. It does not call or route the production helper for
valence-4 faces.

## Frozen Proof State

The harness reads the unchanged six coordinates and eight oriented faces from
`data/fixtures/candidates/closed_valence4_octahedron`. It applies only this
in-memory perturbation for source ID `i`:

```text
dx =  0.017 sin(0.37 (i+1))
dy = -0.013 cos(0.29 (i+1))
dz =  0.019 sin(0.41 (i+1))
```

Fixture CSV files remain unchanged. Exact perturbed coordinates are emitted in
the canonical report.

All eight fixture faces use `s=v,t=w,u=1-v-w` and the three frozen samples
`(v,w)=(1/6,1/6),(1/6,4/6),(4/6,1/6)`. Each sample has quadrature weight
`1/3` and formula factor `1/6`. Rows are
`value,du,dv,duu,dvv,duv,duv`; OpenSubdiv `duv` is duplicated into both mixed
rows. The result covers 24 face-samples.

Rows are keyed to original source IDs `0..5`. A duplicate probe splits each raw
coefficient into `1/4` and `3/4`, reverses the entries, and aggregates in
ascending source-ID order. Row, energy, and force differences are all `0`
against tolerance `1e-12`. The resulting proof-local source aggregation is
three `6x3` arrays, or 18 components per force kind. This is not
`Face::oneRingVertices` production scatter.

## Scalar Oracle

The force sign convention is `F = -grad(E)`. A separate scalar-only path
recomputes each energy without calling the force algebra:

```text
Eb = sum [ (w/2) (k/2) sqa (2H-C0)^2 ], C0 = 0
Ea = 0.5 (uSurf/A0) (A-A0)^2, A0 = 2.75
Ev = 0.5 (uVol/V0) (V-V0)^2, V0 = 0.82
```

`A` and `V` are recomputed at every finite-difference state while nonzero
targets remain fixed. The volume scalar is the full closed-surface
`x dot cross(a1,a2) / 3` functional used by the proof-local `fVolume` algebra.
It is explicitly not equivalent to the legacy visible-volume
`position.x * cross.x` observable and makes no claim about production output
semantics.

For every force kind and all `6 IDs x 3 axes`, centered differences sweep
`h/L={1e-4,3e-5,1e-5,3e-6,1e-6}`, where `L` is the maximum pairwise proof
source distance. Every step must satisfy:

```text
max_abs_residual <= 2e-5 + 2e-6 * max_norm(analytic, finite_difference)
```

All five steps form the required plateau. Across the sweep, worst residuals
were:

| force | max residual | worst ID/axis | analytic | finite difference |
| --- | ---: | --- | ---: | ---: |
| `fBend` | `7.353244912078338e-06` | `5/y` | `-2.108781651810619` | `-2.108789005055531` |
| `fArea` | `6.466578739150464e-08` | `5/y` | `-21.638438418101924` | `-21.638438353436136` |
| `fVolume` | `1.4922081053442282e-09` | `2/y` | `-0.010459455299798883` | `-0.010459453807590778` |

This is 54 unique source-axis comparisons and 270 step evaluations. `C0=0`
gives weaker bending sign coverage; nonzero spontaneous-curvature sign choices
are outside this proof.

## Invariance And Determinism

All source vectors are finite and nonzero for each force kind. Normalized
maximum net-force residuals were `1.741398234840794e-07` bending,
`9.032263028970971e-11` area, and `4.387371952014712e-17` volume. Normalized
maximum torque residuals were `7.046896576037704e-15`,
`1.4989958192460364e-17`, and `1.8874362228622465e-17`, respectively.
Translation and rotational checks pass their emitted scale-aware tolerances.

The probe executes the canonical energy/force report twice and requires
byte-identical output.

## Run

Dependency-absent behavior is an explicit skip:

```bash
scripts/run_irregular_valence4_opensubdiv_force_formula_proof.sh --json
```

Present-dependency proof:

```bash
OPENSUBDIV_ROOT=/tmp/slimed-opensubdiv-install \
OPENSUBDIV_CXXFLAGS='-arch arm64' \
scripts/run_irregular_valence4_opensubdiv_force_formula_proof.sh \
  --json --require-opensubdiv
```

Inventory:

```bash
python3 scripts/inventory_irregular_valence4_force_formula_proof.py --check
```

The pre-existing global inventory failure concerning
`Regular_limit_surface_row_cache.hpp` is baseline drift and is not changed or
claimed by this lane.
