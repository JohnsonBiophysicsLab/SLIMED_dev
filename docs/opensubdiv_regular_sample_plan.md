# OpenSubdiv Regular 12-Control Sample Plan

Date: 2026-06-27.
Baseline: `origin/main` at PR #73 merge commit
`44df0631d959f4377b5a3b60ff45fc1756bc250a`.

This is a docs/scripts/tests-only characterization lane. It does not change
production C++ behavior, C++ backend interfaces, default build policy,
OpenSubdiv dependency policy, vendoring, force formulas, force scatter order,
OpenMP scheduling or reduction, checkpoint/output behavior, propagation,
optimizer behavior, RNG, boundary, ghost, periodic behavior, or production
OpenSubdiv routing.

## Purpose

Before any OpenSubdiv-derived regular rows enter production routing, the
regular sample plan must be exact enough to compare against the current
production formula path. This note freezes the current regular 12-control
sample identity used by SLIMED formulas:

- configured quadrature rows and weights;
- the `s=v,t=w` convention for OpenSubdiv comparison;
- orientation through `firstDerivativeV x firstDerivativeW`;
- seven derivative rows, including the duplicated mixed derivative rows;
- source-id ordering through `Face::oneRingVertices`;
- duplicate source-id aggregation semantics; and
- the comparison boundary required before production routing can change.

This note is evidence/readiness only. It is not production OpenSubdiv routing.

## Frozen Regular Quadrature Rows

The current default `Param::gaussQuadratureN` is `2`. `Mesh` construction calls
`get_gauss_quadrature_weight_VWU(param.gaussQuadratureN, param.VWU,
param.gaussQuadratureCoeff)` and then caches one `7 x 12`
`Param::shapeFunctions[i]` matrix per `Param::VWU` row.

For the regular production formula path, the frozen default sample order is:

| sample | `v` | `w` | `u` | quadrature weight | formula factor |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 | `1/6` | `1/6` | `4/6` | `1/3` | `1/6` |
| 1 | `1/6` | `4/6` | `1/6` | `1/3` | `1/6` |
| 2 | `4/6` | `1/6` | `1/6` | `1/3` | `1/6` |

The formula factor is the current force-path multiplier
`0.5 * param.gaussQuadratureCoeff(i, 0)`. The area/volume calculation also
iterates `param.gaussQuadratureCoeff` in the same cached order.

Any routed OpenSubdiv regular path must either use these same three sample
rows and weights or carry an explicitly reviewed formula/sample change. Ambient
OpenSubdiv availability must not silently change this sample plan.

## Coordinate And Orientation Convention

The regular comparison convention is `s=v,t=w`. Current SLIMED rows are
evaluated from the barycentric triple passed to `get_shapefunction(v,w,u)`.
OpenSubdiv regular rows must be compared under the same convention before
routing.

The orientation boundary is the current tangent cross product:

```text
normal numerator = firstDerivativeV x firstDerivativeW
```

Area integrands, unit normals, mean curvature, bending forces, area forces,
and legacy volume integrands must be compared with this orientation unless a
later reviewed production-routing PR explicitly replaces it.

## Seven Shape Rows

Each regular sample produces a `7 x 12` matrix. Rows are frozen as:

| row index | SLIMED name | Required meaning | OpenSubdiv row for comparison |
| ---: | --- | --- | --- |
| 0 | `position` | limit position | value weights |
| 1 | `firstDerivativeV` | `d/dv` | `du` under `s=v,t=w` |
| 2 | `firstDerivativeW` | `d/dw` | `dv` under `s=v,t=w` |
| 3 | `secondDerivativeVV` | `d2/dv2` | `duu` |
| 4 | `secondDerivativeWW` | `d2/dw2` | `dvv` |
| 5 | `mixedDerivativeVW` | `d2/dvdw` | `duv` |
| 6 | `mixedDerivativeWV` | `d2/dwdv` | `duv` |

Rows 5 and 6 currently duplicate the mixed derivative in the regular shape
function implementation. A production backend must preserve this duplicated
mixed-row convention or document and test a reviewed replacement before
changing routing.

## Source-Id Order And Duplicate Aggregation

For a regular 12-control face, local shape-function column `j` addresses
`Face::oneRingVertices[j]`. The current production force scatter also lands
local regular force row `j` on `face.oneRingVertices[j]`.

The backend-neutral row-weight seam must expose weights keyed by original
SLIMED source ids. The current regular implementation preserves the supplied
source-id order and answers:

```text
row_weight(SLIMED derivative row, original SLIMED vertex id)
```

If duplicate source ids appear, `row_weight(...)` sums every matching local
column deterministically. A routed OpenSubdiv path must aggregate duplicate
source-id contributions before comparing rows, formulas, or scatter behavior.

## Comparison Boundary Before Routing

A future production-routing PR can use this sample plan only after proving all
of the following against the current direct regular route:

- the exact three quadrature rows, weights, and `0.5 * weight` formula factors;
- the `s=v,t=w` derivative convention and orientation;
- all seven derivative rows for every sample, including rows 5 and 6;
- source ids matching `Face::oneRingVertices[j]` or an explicitly reviewed
  replacement order;
- deterministic aggregation of duplicate source-id contributions;
- actual `fBend`, `fArea`, and `fVolume` row comparison through the production
  formulas;
- output-visible energy, normal, mean-curvature, area, and legacy-volume
  comparison at production call timing; and
- scatter through `Face::oneRingVertices` with the current serial/OpenMP
  reduction contract or a reviewed replacement.

The existing OpenSubdiv probes and in-tree regular evaluator tests are
prerequisite evidence. They are not approval to route production faces through
OpenSubdiv.

## Cross-References

- `docs/opensubdiv_routing_readiness_map.md` records the broader routing gate.
- `docs/opensubdiv_mapping_contract.md` records the backend-neutral seven-row
  and source-id contract.
- `docs/opensubdiv_force_transpose_evidence.md` separates row/integrand,
  toy-transpose, and actual formula evidence.
- `docs/force_formula_scatter_equivalence.md` records the current
  force/scatter formula contract.
- `docs/opensubdiv_regular_backend_adapter_readiness.md` ties this frozen
  sample plan to the regular backend-adapter pre-routing checklist.

## Inventory Check

Run the regular sample-plan inventory with:

```console
python3 scripts/inventory_opensubdiv_regular_sample_plan.py --check
```

The inventory is source-text based and dependency-free. A missing anchor means
the regular sample-plan evidence has drifted enough to need human review
before a future OpenSubdiv routing PR uses it as a gate.
