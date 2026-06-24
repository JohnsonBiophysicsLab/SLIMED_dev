# Irregular Subdivision Transpose Proof Map

Date: 2026-06-24.
Baseline: `363d6669835d864e43078abd5a9e70a73562286b` plus merged PR #59.

This is the evidence map that preceded the narrow production 11-control
subdivision/back-projection route. The production route now supports the
documented `11 = 4+3+4` case when `Param::subDivideTimes > 0` by reusing the
existing irregular subdivision matrices, evaluating regular child patches, and
transposing child force rows back to the original one-ring controls. It still
does not change default builds, OpenSubdiv dependency policy, regular
12-control formulas, scatter order, OpenMP accumulation, checkpoint/output
behavior, propagation behavior, or optimizer behavior.

## Current Boundary

The production route still rejects unsupported non-boundary 11-control
membrane force requests with zero subdivision depth before the membrane OpenMP
face loop. That guard is intentional. Supported 11-control requests use the
same child-patch subdivision plan as the existing area/volume path; they do not
route production irregular faces through OpenSubdiv or through the regular
12-control helper as a direct fallback.

The useful future contract has three separate layers:

| Layer | Current evidence | Status |
| --- | --- | --- |
| Regular row/integrand equivalence | `--regular-equivalence-report` compares OpenSubdiv regular value/derivative rows, tangent cross product, unit normal, area integrand, and legacy volume integrand against frozen SLIMED regular evaluator values. | Proven only for the documented regular lattice samples within tolerance. |
| Regular transpose shape | `--force-transpose-report` checks `g dot (W p) == (W^T g) dot p` for OpenSubdiv's regular rows and a SLIMED-compatible seven-row toy shape. | Proven only for a toy scalar functional, not production force formulas. |
| Irregular source coverage and transpose shape | The production 11-control route transposes regular child-patch force rows through existing subdivision matrices. `--aggregate-source-coverage-report` and `--irregular-transpose-proof-map-report` remain OpenSubdiv-only observational evidence. | Production-supported only for the existing subdivision-matrix 11-control path; OpenSubdiv evidence remains observational. |

## Source-Id Transpose Shape

For one OpenSubdiv sample, let `W` be the matrix of value and derivative row
weights keyed by original control id, and let `p` be the original control
coordinates. A sample-space row gradient `g` back-projects by the ordinary
linear transpose:

```text
g dot (W p) == (W^T g) dot p
```

For the SLIMED-compatible seven-row shape used by the opt-in probe:

| SLIMED row | OpenSubdiv row used by the probe | Production status |
| --- | --- | --- |
| position | value weights | Regular toy transpose only. |
| `d/dv` | `du` under observed `s=v,t=w` mapping | Regular toy transpose only. |
| `d/dw` | `dv` under observed `s=v,t=w` mapping | Regular toy transpose only. |
| `d2/dv2` | `duu` | Regular toy transpose only. |
| `d2/dw2` | `dvv` | Regular toy transpose only. |
| `d2/dvdw` | `duv` | Mixed-row duplication needs production review. |
| `d2/dwdv` | `duv` | Mixed-row duplication needs production review. |

In the production subdivision-matrix route, a regular child patch is represented
as `child = A * original11`, and child local force rows back-project by
`A^T * childForce` into the original 11 rows addressed by
`Face::oneRingVertices[k]`. A future OpenSubdiv backend still needs an
explicitly reviewed source-id and sample-plan mapping before it can replace or
augment that route.

## What Is Proven For Regular Rows

The regular evidence proves the following limited facts for the documented
regular triangular lattice samples:

- OpenSubdiv row values match `SlimedLoopLimitSurfaceEvaluator` rows under
  `s=v,t=w`, including the current duplicated mixed-row convention.
- Derived tangent cross product, unit normal, area integrand, and the current
  legacy volume integrand match frozen SLIMED outputs within the documented
  tolerance.
- A deterministic toy sample-space gradient can be transposed from regular
  OpenSubdiv row weights back to the same 12 original source ids used by the
  regular one-ring evaluator.

This still does not prove production bending, area, or volume force formula
equivalence. The production force lane must transpose through the actual
`element_energy_force_regular(...)` formulas and verify the resulting local
force rows and scatter.

## What Is Only Observational For 11 Controls

The orientation-normalized 11-control fixture can expose all original fixture
ids `0..10` when source coverage is aggregated across every ptex face and the
documented nine-point sample grid. The same aggregate plan can be checked as a
toy stacked transpose:

```text
sum_samples g dot (W_sample p)
  == p dot sum_samples (W_sample^T g)
```

This is useful because it confirms that the fixture controls are visible to
OpenSubdiv value, first-derivative, second-derivative, and toy transpose
weights at the aggregate level.

The OpenSubdiv aggregate evidence remains observational because:

- it does not select which ptex faces/sample points should represent one
  production SLIMED irregular face;
- it does not prove that all adjacent ptex samples should contribute to one
  face force;
- it does not map aggregate source ids into the exact SLIMED irregular
  `Face::oneRingVertices` ordering used by production scatter;
- it does not pass through bending, area, or volume force formulas;
- it does not characterize quadrature weights or child-patch accumulation
  order for irregular force routing; and
- it does not change the production subdivision-matrix 11-control force route
  or the zero-depth unsupported guard.

## Opt-In Probe Commands

Default validation remains dependency-free:

```bash
python3 scripts/probe_opensubdiv_feasibility.py --json
python3 scripts/probe_opensubdiv_feasibility.py --mode check
```

With a user-provided OpenSubdiv install, the aggregate proof-map report is:

```bash
OPENSUBDIV_ROOT=/path/to/opensubdiv \
python3 scripts/probe_opensubdiv_feasibility.py \
  --json --require-opensubdiv --irregular-transpose-proof-map-report
```

The report is expected to emit `irregular_transpose_proof_map` for each
11-control fixture variant. The orientation-normalized fixture is the relevant
one for future evidence. The compact unoriented fixture may still report
missing controls because that topology is intentionally retained as an
artifact case.

## Production-Readiness Checklist

Before replacing or broadening the current subdivision-matrix irregular force
support, a production PR needs explicit evidence for each item below:

| Gate | Required evidence before replacing or broadening 11-control force routing |
| --- | --- |
| Derivative convention | Approved `s,t` to SLIMED `v,w,u` mapping, including sign/order and mixed-row convention. |
| Source-id coverage | Fixture-level source ids prove the exact controls needed by the selected production sample plan, not only aggregate all-ptex visibility. |
| Transpose/back-projection shape | Current subdivision-matrix route transposes regular child-patch forces through child-to-original weights; any backend replacement must transpose through original SLIMED vertex ids or an approved child-patch local-id map. |
| Production force formulas | Bending, area, and volume formula outputs match the current regular path on regular fixtures before irregular routing is added. |
| Scatter order | Local force components scatter through `Face::oneRingVertices` in the reviewed order, or a reviewed irregular replacement order is documented and tested. |
| Quadrature/sample selection | The ptex faces, child patches, sample coordinates, and quadrature weights representing one SLIMED irregular face are fixed and tested. |
| Equivalence tolerance | Serial and OpenMP force, energy, normal, area, and volume tolerances are stated with fixtures and comparison commands. |
| Fallback/guard policy | Unsupported irregular, boundary, ghost, periodic, and dependency-absent routes fail or fall back only through reviewed diagnostics. |
| Dependency policy | Default builds remain OpenSubdiv-free until an approved opt-in or production dependency lane changes that policy. |

## Next Gated Production Prompt

```text
Extend validation for the production 11-control subdivision/back-projection
route and keep OpenSubdiv out of default builds. Prove serial/OpenMP numerical
behavior on representative fixtures while preserving quadrature order,
derivative convention, mixed-row policy, scatter order, thread-local force
buffer shape, reduction order, boundary/ghost/periodic policy, legacy volume
semantics, outputs, checkpoints, RNG behavior, propagation timing, optimizer
timing, and accepted-step behavior. Do not replace the current production
11-control subdivision-matrix route with OpenSubdiv in this PR.
```

After that proof is accepted, a separate backend prompt can choose an
OpenSubdiv sample/child-patch plan and compare it against the current
subdivision-matrix route.
