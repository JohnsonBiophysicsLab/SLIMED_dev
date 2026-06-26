# OpenSubdiv Sample/Source-Id/Back-Projection Mapping Contract

Date: 2026-06-26.
Baseline: `origin/main` at `bc28bc1bd8693a27c8616eeb0300060335e6ffab`
after PR #68.

This is a docs/scripts-only contract lane. It does not change production C++
behavior, default build policy, dependency policy, vendoring, OpenSubdiv
production routing, force formulas, force scatter order, OpenMP behavior,
checkpoint/output behavior, propagation behavior, or optimizer behavior.

## Purpose

Before an OpenSubdiv backend can be routed into production, SLIMED needs a
reviewed mapping contract from backend samples to the current force code. The
contract must answer three questions without exposing OpenSubdiv types at
production call sites:

- Which OpenSubdiv ptex faces, child patches, sample coordinates, and
  quadrature weights represent one SLIMED face?
- Which original SLIMED vertex ids provide each value, first-derivative, and
  second-derivative row weight at each sample?
- How are sample-space bending, area, and volume force gradients transposed
  back into SLIMED source ids and then scattered through the current
  `Face::oneRingVertices` order?

The current `LimitSurfaceEvaluator::evaluate_weighted(...)` seam remains
backend-neutral. The public contract is evaluated seven-row SLIMED samples plus
row weights keyed by SLIMED source ids. OpenSubdiv patch-table, ptex, stencil,
and patch-control details must stay behind a backend implementation until a
separate production routing PR is reviewed.

## Non-Goals

This contract does not approve or implement:

- OpenSubdiv C++ integration hooks;
- default Makefile or dependency changes;
- vendoring, submodules, generated third-party artifacts, or package-manager
  assumptions;
- production OpenSubdiv backend routing;
- changes to bending, area, volume, quadrature, scatter, or reduction formulas;
- changes to checkpoint/output, propagation, optimizer, RNG, boundary, ghost,
  or periodic policy; or
- any scientific claim that irregular forces are physically validated.

Default builds remain OpenSubdiv-free. OpenSubdiv-present evidence stays
opt-in through the existing probe wrapper and a user-provided
`OPENSUBDIV_ROOT`.

## Backend-Neutral Row Contract

Every backend sample must expose the current seven SLIMED derivative rows:

| SLIMED row | Required meaning | OpenSubdiv row to map before review |
| --- | --- | --- |
| `position` | limit position | value weights |
| `firstDerivativeV` | `d/dv` | `du` under the observed `s=v,t=w` mapping |
| `firstDerivativeW` | `d/dw` | `dv` under the observed `s=v,t=w` mapping |
| `secondDerivativeVV` | `d2/dv2` | `duu` |
| `secondDerivativeWW` | `d2/dw2` | `dvv` |
| `mixedDerivativeVW` | `d2/dvdw` | `duv`, if mixed-row duplication is reviewed |
| `mixedDerivativeWV` | `d2/dwdv` | `duv`, if mixed-row duplication is reviewed |

The observed regular prototype mapping is `s=v,t=w`; future production code
must still record this as an explicit derivative convention, including
orientation, sign, row order, and the current duplicated mixed-row convention.
Returning evaluated coordinates without row weights is insufficient for force
work.

## Source-Id Contract

Source ids at the public backend boundary must be original SLIMED vertex ids,
not OpenSubdiv-internal patch-control indices or transient stencil offsets.
Each sample must provide row weights addressable as:

```text
row_weight(SLIMED derivative row, original SLIMED vertex id)
```

For regular 12-control faces, those ids must match the current
`Face::oneRingVertices` support used by `SlimedLoopLimitSurfaceEvaluator`.
If a backend proposes a different ordering, the PR must document and test how
that replacement order preserves or deliberately replaces current scatter
semantics.

For irregular faces, aggregate all-ptex source visibility is useful evidence
but not a face-level force contract. A backend must state the exact ptex faces,
child patches, sample coordinates, and quadrature weights that represent one
SLIMED face, then prove that the selected plan covers the required source ids
for that face.

## Back-Projection Contract

For one sample, the row-weight map is a linear map from original SLIMED control
coordinates to evaluated rows. A sample-space gradient must transpose through
that map:

```text
g dot (W p) == (W^T g) dot p
```

Here `W` contains value and derivative row weights keyed by original SLIMED
vertex id, `p` is the original control-coordinate vector, and `g` is the
sample-space gradient. The opt-in OpenSubdiv probe has shown this shape for a
toy scalar functional, but a production backend must prove it through the
actual SLIMED bending, area, and volume force formulas.

The required evidence before routing is:

- regular row and integrand equivalence against `SlimedLoopLimitSurfaceEvaluator`;
- production force transpose/back-projection through the actual bending, area,
  and volume formulas, not only a toy gradient;
- local force rows that scatter through `Face::oneRingVertices[j]` or an
  explicitly reviewed replacement order;
- preservation or reviewed replacement of the current thread-local force
  buffer shape and ascending thread-index reduction order;
- serial/OpenMP tolerances for energies, forces, normals, area, and volume on
  approved fixtures; and
- dependency-absent and unsupported-topology diagnostics that do not silently
  route through an unapproved fallback.

## Current Irregular Boundary

The current production route is still the dependency-free positive-depth
`11 = 4+3+4` subdivision-matrix path. It evaluates regular child patches and
transposes child bending, area, and volume force rows through the existing
child-to-original subdivision weights before scattering to the 11 original
`Face::oneRingVertices` entries.

That route is not OpenSubdiv-backed. It does not approve broader irregular
topologies, zero-depth 11-control requests, or dependency-present behavior
that differs from dependency-absent behavior. Zero-depth 11-control requests
and unsupported irregular topologies remain guarded unsupported cases.

Any OpenSubdiv replacement for this route must compare against the current
subdivision-matrix transpose/back-projection route where that route applies,
or record an explicit reviewer-approved waiver.

## Inventory Check

Run the docs-anchor inventory with:

```console
python3 scripts/inventory_opensubdiv_mapping_contract.py --fail-on-missing
```

The script is intentionally source-text based. Missing anchors mean the docs
have drifted enough that this contract needs human review before it is used as
a gate for production OpenSubdiv routing.
