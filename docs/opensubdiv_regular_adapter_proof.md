# OpenSubdiv Regular Adapter Proof

Date: 2026-06-29.
Baseline: PR #75 merge commit
`0a495ef0e3ef6370f5e73892b987e356d9bc4f46`.

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
- `Face::oneRingVertices` scatter identity for those actual force rows.

This proves an experimental adapter boundary can produce the reviewable
weighted-sample contract for the regular fixture. It does not approve any
production route to consume OpenSubdiv-derived rows.

## Remaining Gate

Before production routing can change, a later reviewed PR must still compare
OpenSubdiv-derived rows against production call timing and scatter in the real
C++ route, including output-visible state and serial/OpenMP accumulation
behavior. This proof is prerequisite evidence only.
