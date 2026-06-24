# Force Formula And Scatter Equivalence Contract

Date: 2026-06-24.
Baseline: `origin/main` at `20f49d9fb47f419aecf41e7e91f05e725464b07f`
after PR #54.

This is a characterization lane. It does not change production C++ behavior,
default build policy, OpenSubdiv dependency policy, force formulas, force
scatter ordering, OpenMP behavior, backend routing, checkpoint/output formats,
or `LimitSurfaceEvaluator` behavior.

## Current Regular Force Formula Inputs

`Mesh::element_energy_force_regular(...)` consumes the current regular
`12 x 3` one-ring coordinate matrix and each cached `Param::shapeFunctions[i]`
matrix in quadrature order. The production 12-control branch opts into
`LimitSurfaceWeightedSample`, which stores the same seven shape rows as row
weights keyed by `Face::oneRingVertices` source ids. In the regular case,
`SlimedLoopLimitSurfaceEvaluator::evaluate_weighted_shape_function(...)` maps
the seven shape rows into the existing local variables:

| Evaluator field | Shape row | Local variable | Formula use |
| --- | ---: | --- | --- |
| `position` | 0 | `x` | Volume term only. |
| `firstDerivativeV` | 1 | `a_1` | Bending geometry, area force, and volume force. |
| `firstDerivativeW` | 2 | `a_2` | Bending geometry, area force, and volume force. |
| `secondDerivativeVV` | 3 | `a_11` | Bending normal/basis derivative formulas and `da1`. |
| `secondDerivativeWW` | 4 | `a_22` | Bending normal/basis derivative formulas and `da2`. |
| `mixedDerivativeVW` | 5 | `a_12` | Bending `xa_2`, `a22`, and `da2` terms. |
| `mixedDerivativeWV` | 6 | `a_21` | Bending `xa_1`, `a11`, and `da1` terms. |

The current production formula then derives `a_3`, `a_31`, `a_32`, `a1`,
`a2`, `a11`, `a12`, `a21`, and `a22` from those rows. It loops over local
controls `j = 0..11` and writes three local force matrices:

| Local output | Formula source | Shape rows used directly in the per-control loop |
| --- | --- | --- |
| `fBend(j,:)` | `tempf_be`, quadrature-accumulated from `f_be` | Rows `1`, `2`, `3`, `4`, `5`, and `6` through `n1_be`, `n2_be`, `m1_be`, `m2_be`, `da1`, and `da2`. |
| `fArea(j,:)` | `tempf_cons`, quadrature-accumulated from `f_cons` | Rows `1` and `2` through `n1_cons * sf(1,j) + n2_cons * sf(2,j)`. |
| `fVol(j,:)` | `tempf_conv`, quadrature-accumulated from `f_conv` | Rows `0`, `1`, and `2` through `n1_conv`, `n2_conv`, and `tmp_evol * sf(0,j) * a_3`. |

The local outputs are accumulated in sample order using
`0.5 * param.gaussQuadratureCoeff(i, 0)`. Bending energy, mean curvature, and
the face normal use the same quadrature order.

## Regular Back-Projection Slice

The approved production slice adds a backend-neutral row/source-id abstraction
without changing regular formula semantics. For 12-control production faces,
`accumulate_membrane_face_energy_and_forces(...)` calls
`element_energy_force_regular(...)` with regular back-projection enabled. The
helper builds a `LimitSurfaceWeightedSample` from the current cached
`Param::shapeFunctions[i]`, current `12 x 3` control matrix, and current
`Face::oneRingVertices` ids.

Inside the existing per-control loop, the force formula still evaluates local
rows `j = 0..11` in order. Each `sf(row, j)` use is represented by the same
numeric row weight looked up as:

```text
weightedSample.row_weight(row, face.oneRingVertices[j])
```

The legacy direct path remains callable without the opt-in flag and remains the
control comparator for deterministic regular fixtures. The 11-control branch is
not routed through this abstraction; it keeps the existing unsupported fallback
into the direct helper path.

## Local Rows And Scatter Order

For regular faces, `Face::oneRingVertices` is constructed in the existing
`d1..d12` order:

```text
{d1, d2, d3, d4, d5, d6, d7, d8, d9, d10, d11, d12}
```

`accumulate_membrane_face_energy_and_forces(...)` first copies vertex
coordinates in that order. After `element_energy_force_regular(...)` returns,
local row `j` scatters to the mesh vertex id stored in
`face.oneRingVertices[j]`.

For each target vertex, the flat per-thread force buffer stores nine
components:

```text
base + 0..2 -> fBend(j, 0..2) -> Vertex::force.forceCurvature
base + 3..5 -> fArea(j, 0..2) -> Vertex::force.forceArea
base + 6..8 -> fVol(j, 0..2) -> Vertex::force.forceVolume
```

The characterization test
`SurfaceLimitSurfaceEvaluatorContract.RegularForceRowsScatterInOneRingOrder`
uses a deliberately permuted 12-control one-ring fixture. It calls
`element_energy_force_regular(...)` directly, then calls the production
`Compute_Energy_And_Force()` path on the same one-face fixture and verifies
that every vertex force component equals the local force row addressed by
`face.oneRingVertices[j]`. Because production regular faces now opt into
row/source-id back-projection, this test also compares direct shape-row force
outputs against the back-projected production scatter. The focused
`RegularForceBackProjectionMatchesDirectShapeWeights` test compares the full
local bending, area, volume, energy, mean-curvature, and normal outputs for
deterministic fixtures under natural and permuted source-id order.

## Serial And OpenMP Accumulation Shape

The membrane face loop allocates:

```text
faceForceComponents[nThreads][nVertices * 9]
```

Each face writes only into the buffer for its current thread. After the face
loop, a separate vertex loop reduces thread buffers in ascending
`threadIndex = 0..nThreads-1` order and writes `forceCurvature`, `forceArea`,
and `forceVolume`.

The default serial shape is the same data structure with `nThreads = 1`.
With OpenMP enabled, this lane does not characterize scheduler assignment as a
portable numerical guarantee. A future backend must preserve the same
thread-local buffer shape and reduction order unless a review explicitly
approves a changed floating-point accumulation contract.

Face-side writes inside the membrane loop are also part of the current
contract:

- `Face::energy.energyCurvature`
- `Face::meanCurvature`
- `Face::normVector`

Boundary faces are skipped by the membrane face loop. Ghost faces are skipped
earlier by the geometry refresh path.

## Inventory Script

Regenerate the source-anchor inventory with:

```console
python3 scripts/inventory_force_formula_scatter_contract.py
```

Use the missing-anchor gate when this contract is part of validation:

```console
python3 scripts/inventory_force_formula_scatter_contract.py --fail-on-missing
```

The script is intentionally not a C++ parser. It records the production source
anchors for evaluator row copies, local force outputs, local-to-vertex scatter,
component buffer layout, and thread-buffer reduction order. Missing anchors
mean the source has moved enough that a human should refresh this contract
before relying on it as an OpenSubdiv backend gate.

## Relationship To PR #54 OpenSubdiv Evidence

PR #54 showed that OpenSubdiv's regular value and derivative weights can be
transposed for a toy scalar functional at the same regular samples, and that a
SLIMED-compatible seven-row toy gradient can duplicate OpenSubdiv's single
mixed derivative row into SLIMED's two mixed rows. That proof established a
linear algebra shape:

```text
g dot (W p) == (W^T g) dot p
```

This lane characterizes the remaining production-side gate: which evaluated
rows feed bending, area, and volume force terms; how local 12-control force
rows map back to `Face::oneRingVertices`; and how serial/OpenMP accumulation
currently writes mesh force buffers.

What remains before backend work:

- a reviewed backend interface that can expose the needed row weights and
  source vertex ids without changing production behavior;
- production force transpose/back-projection equivalence for the actual
  bending, area, and volume formulas, not just a toy gradient;
- explicit preservation or review-approved replacement of scatter order,
  thread-local accumulation shape, and reduction order;
- irregular face-level force support over the 11-control fixture;
- boundary, ghost, periodic, and volume-policy review; and
- OpenSubdiv dependency, license, and default build policy review.
