# OpenSubdiv Regular Adapter Proof

Date: 2026-06-29.
Baseline: PR #77 merge commit
`5abeedfe2caa6080b9d418989dba092d03912e6d`.

This is a scripts/docs/tests-only proof lane. It does not change production C++
behavior, default `make` or test behavior, OpenSubdiv dependency policy,
force formulas, quadrature, row order, mixed-row duplication,
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
per-vertex scatter layout.

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
- `Face::oneRingVertices` scatter identity for those actual force rows; and
- proof-local production-call shadow evidence for the 12-column input,
  seven-row weighted sample, 12x3 force matrix, and 9-component scatter shape.

This proves an experimental adapter boundary can produce the reviewable
weighted-sample contract for the regular fixture. It does not approve any
production route to consume OpenSubdiv-derived rows.

## Remaining Gate

Before production routing can change, a later reviewed PR must still compare
OpenSubdiv-derived rows against production call timing and scatter in the real
C++ route, including output-visible state and serial/OpenMP accumulation
behavior. This proof is prerequisite evidence only.
