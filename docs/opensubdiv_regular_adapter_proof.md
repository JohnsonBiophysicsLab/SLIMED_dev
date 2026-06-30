# OpenSubdiv Regular Adapter Proof

Date: 2026-06-29.
Baseline: PR #81 merge commit
`9971f22953ff9adefd078dafbd5f4447e4a877d4`.

This is a docs/scripts/tests/experiments-only proof lane. It does not change
production C++ behavior, default `make` or test behavior, OpenSubdiv dependency
policy, force formulas, quadrature, row order, mixed-row duplication,
`Face::oneRingVertices` scatter, OpenMP buffer/reduction behavior,
checkpoint/output, propagation, optimizer/RNG, boundary/ghost/periodic
behavior, or production OpenSubdiv routing.

## Purpose

The opt-in probe now has a review-gated regular adapter proof report:

```console
OPENSUBDIV_ROOT=/tmp/slimed-opensubdiv-install \
OPENSUBDIV_CXXFLAGS='-arch arm64' \
scripts/run_opensubdiv_probe.sh \
  --json --require-opensubdiv \
  --regular-equivalence-report \
  --force-transpose-report \
  --regular-actual-force-report \
  --regular-adapter-proof-report
```

The new `--regular-adapter-proof-report` path compiles only the temporary
OpenSubdiv probe program. It emits `kind:
test_only_regular_opensubdiv_adapter_proof` and remains inert unless
`OPENSUBDIV_ROOT` is supplied by the caller.

## Experimental C++ Harness

This lane also adds a standalone experimental C++ proof harness:

```console
OPENSUBDIV_ROOT=/tmp/slimed-opensubdiv-install \
OPENSUBDIV_CXXFLAGS='-arch arm64' \
scripts/run_opensubdiv_regular_cpp_adapter_proof.sh \
  --json --require-opensubdiv
```

The harness lives in
`experiments/opensubdiv_regular_cpp_adapter_proof.cpp`, is compiled only by the
explicit wrapper, and emits `kind:
test_only_regular_opensubdiv_cpp_adapter_proof`. It maps OpenSubdiv regular
limit stencils into a proof-local `LimitSurfaceWeightedSample`-style shape:
seven rows, original SLIMED source ids, frozen regular sample coordinates,
`s=v,t=w`, duplicated mixed rows, and deterministic duplicate aggregation.
It now also feeds those adapter-remapped rows into a proof-only local copy of
the current regular bending, area, and volume sample algebra and emits finite,
nonzero `fBend`, `fArea`, and `fVolume` rows plus `Face::oneRingVertices`
scatter identity. The report also includes a production-call shadow section
that compares the proof-local OpenSubdiv-derived rows against the current
regular production call shape: 12 one-ring coordinate columns in
`Face::oneRingVertices[j]` order, seven derivative rows, 12x3 local
`fBend`/`fArea`/`fVolume` force matrices, and the current 9-component
per-vertex scatter layout. After PR #79, the report also emits
`production_helper_dry_run`: a proof-local call to the current
`Mesh::element_energy_force_regular` helper with the OpenSubdiv-derived regular
rows installed only on a local `Param::shapeFunctions` instance. That dry-run
compares the live helper output against the proof-local force algebra rows and
reports the maximum force-row and scalar differences. This lane adds
`visible_observable_dry_run` as a second proof-local dry-run that calls the
current regular `Mesh::calculate_element_area_volume` output path with the same
OpenSubdiv-derived rows installed only on a local `Param`, then compares
visible regular area and legacy visible-volume values against proof-local row
evaluation. This lane also adds `serial_openmp_accumulation_parity`: a
proof-local comparison between direct serial scatter and the OpenMP-style
per-thread force-buffer accumulation/reduction shape used by
`accumulate_membrane_face_energy_and_forces`, fed by the same
OpenSubdiv-derived regular `fBend`/`fArea`/`fVolume` rows.

This C++ harness does not add a Makefile target, default dependency,
production route, production include, public SLIMED signature, or OpenSubdiv
type at any production call site. It is evidence that the regular rows can be
adapted into the existing weighted-sample contract, not approval to route
production faces through OpenSubdiv.

## Production-Call Shadow Evidence

The C++ report emits `production_call_shadow` as an explicitly proof-local
comparison against the current regular production-call shape. It verifies that
the OpenSubdiv-derived weighted rows are keyed in the same source-id order that
production passes as `coordOneRingVertices[j]`, that the proof produces local
force rows with the current 12x3 matrix shape, and that row `j` scatters to
`Face::oneRingVertices[j]` using the same 9-component force-buffer layout:
`fBend` offsets `0..2`, `fArea` offsets `3..5`, and `fVolume` offsets `6..8`.

This is shadow evidence only. It does not call the production helper with
OpenSubdiv data, does not alter the regular helper, and does not change default
serial or OpenMP accumulation behavior.

## Production-Helper Dry-Run Evidence

The C++ report emits `production_helper_dry_run` as prerequisite evidence
against the current regular production helper semantics. The harness constructs
a local `Param`, replaces only that local instance's `shapeFunctions` and
quadrature coefficients with the OpenSubdiv-derived regular rows from the
frozen sample plan, sets the same proof-local area/volume totals, and calls
`Mesh::element_energy_force_regular` in the temporary proof binary. The emitted
JSON states:

- `not_production_routing:true`;
- `production_api:"Mesh::element_energy_force_regular"`;
- `open_subdiv_rows_used_as_local_shape_functions:true`;
- `default_build_dependency_added:false`;
- `route_installed_in_production:false`;
- the regular 12-control and three-sample dimensions; and
- max force-row/scalar differences versus the proof-local formula rows.

This is still not production routing readiness by itself. It does not route a
real production face through OpenSubdiv, does not alter the helper signature,
and does not establish serial/OpenMP routed accumulation or output-visible
state parity.

## Visible Observable Dry-Run Evidence

The C++ report emits `visible_observable_dry_run` as prerequisite
output-visible evidence for the current regular area/volume path. The harness
constructs a local mesh, installs the OpenSubdiv-derived regular rows only on
that local `Param`, calls the current regular 12-control
`Mesh::calculate_element_area_volume` path, and compares:

- proof-local area against production regular `Face::elementArea`;
- proof-local `legacy_visible_volume` against production regular
  `Face::elementVolume`;
- the force fixture's full-dot volume as a separately labeled value; and
- a pass flag and maximum area/volume difference.

The `legacy_visible_volume` label is intentional: the current production
regular area/volume path preserves its existing x-component quadrature
convention for volume. This evidence characterizes that visible output; it does
not redefine volume semantics, prove scientific equivalence, or approve routing
production faces through OpenSubdiv.

## Serial/OpenMP Accumulation Parity Evidence

The C++ report emits `serial_openmp_accumulation_parity` as proof-only
accumulation evidence. It starts from the already proven OpenSubdiv-derived
regular force rows, scatters them through `Face::oneRingVertices[j]`, and
compares:

- a direct serial `nVertices*9` force-buffer accumulation; against
- simulated OpenMP per-thread `nVertices*9` force buffers reduced by vertex,
  force component, and thread index.

The emitted JSON states `not_production_routing:true`,
`default_build_dependency_added:false`, `route_installed_in_production:false`,
the current 9-component force-buffer shape, the maximum serial/OpenMP-style
accumulation difference, finite/nonzero checks, and
`matches_serial_openmp_accumulation_shape`.

This is a local shape/tolerance proof only. It does not change production
OpenMP pragmas, thread-buffer allocation, reduction ordering, force formulas,
scatter order, Makefile defaults, or dependency behavior.

## Proof Boundary

For the regular lattice fixture, the report remaps OpenSubdiv stencil rows into
the existing SLIMED weighted-sample shape:

```text
sample coordinates: frozen regular quadrature rows
OpenSubdiv coordinates: s=v,t=w
rows: position, d/dv, d/dw, d2/dv2, d2/dw2, d2/dvdw, d2/dwdv
source ids: original SLIMED vertex ids
local scatter order: Face::oneRingVertices[j]
```

The proof intentionally observes that OpenSubdiv stencil source order differs
from the SLIMED one-ring order. The adapter proof therefore compares by
original source id, not by transient OpenSubdiv stencil index.

## Evidence Emitted

The report records all of the following as machine-readable JSON:

- frozen regular quadrature rows, weights, and `0.5 * weight` formula factors;
- the `s=v,t=w` coordinate convention;
- seven SLIMED rows, with OpenSubdiv `duv` duplicated for both mixed rows;
- original source ids matching the regular face `Face::oneRingVertices` set;
- exact adapter-remapped row evaluation versus the OpenSubdiv stencil
  evaluation;
- deterministic duplicate source-id aggregation;
- actual finite, nonzero `fBend`, `fArea`, and `fVolume` row evidence from the
  local copy of the current force algebra; and
- `Face::oneRingVertices` scatter identity for those actual force rows;
- proof-local production-call shadow evidence for the 12-column input,
  seven-row weighted sample, 12x3 force matrix, and 9-component scatter shape;
  and
- proof-local production-helper dry-run parity against
  `Mesh::element_energy_force_regular` using OpenSubdiv-derived regular rows in
  a local `Param`; and
- proof-local visible observable dry-run parity for regular area and current
  legacy visible volume using OpenSubdiv-derived regular rows in a local
  `Param`; and
- proof-local serial/OpenMP-style accumulation parity for the current
  `nVertices*9` force-buffer scatter/reduction shape.

This proves an experimental adapter boundary can produce the reviewable
weighted-sample contract for the regular fixture. It does not approve any
production route to consume OpenSubdiv-derived rows.

## Remaining Gate

Before production routing can change, a later reviewed PR must still compare
OpenSubdiv-derived rows against routed production call timing and scatter in
the real C++ route, including output-visible state beyond this regular
area/volume characterization and serial/OpenMP accumulation behavior. This
proof is prerequisite evidence only.
