# Guarded regular OpenSubdiv route performance

This document records the cost of the guarded regular OpenSubdiv production
route after PR #105 and the cache correction completed by PR #109. It does not
change routing, formulas, scatter order, OpenMP reductions, output,
checkpointing, or propagation.

## Reproducible comparison

Build one executable with the explicit OpenSubdiv compile-time gate, then run
the same binary in both modes:

```bash
make clean
make -B omp USE_OPENSUBDIV_REGULAR=1 OPENSUBDIV_ROOT=/path/to/opensubdiv
python3 scripts/benchmark_opensubdiv_regular_route.py \
  --executable ./bin/continuum_membrane \
  --l-face 12.5,7.5,5 \
  --threads 1,4 \
  --repeats 3 \
  --output /tmp/slimed-opensubdiv-route-performance.json
```

The direct measurements remove `SLIMED_USE_OPENSUBDIV_REGULAR`; routed
measurements set it to `1`. Both modes therefore use the same executable,
compiler, OpenSubdiv build, parameter fixture, and `OMP_NUM_THREADS` value.
Each run uses an isolated scratch directory, and direct/routed ordering
alternates by round to reduce filesystem carryover and ordering bias.
The benchmark fixture is deterministic and explicitly not a scientific
protocol.

## PR #105 baseline measurement

The following local characterization used merge commit `caf7c351`, GCC 15.2,
OpenSubdiv 3.7.0 built with the same GCC toolchain, and the deterministic
eight-iteration benchmark fixture on arm64 macOS. Each value is the mean of
three measured runs after one warmup. These numbers characterize this machine;
they are not a scientific acceptance threshold.

| `lFace` | Threads | Direct (s) | Routed (s) | Routed/direct |
|---:|---:|---:|---:|---:|
| 12.5 | 1 | 0.0700 | 0.2811 | 4.02x |
| 12.5 | 4 | 0.0547 | 0.2776 | 5.07x |
| 7.5 | 1 | 0.4262 | 2.9097 | 6.83x |
| 7.5 | 4 | 0.2013 | 2.7398 | 13.61x |
| 5.0 | 1 | 1.3657 | 14.0330 | 10.28x |
| 5.0 | 4 | 0.5444 | 13.6691 | 25.11x |

The direct path benefits substantially from four threads as the mesh grows.
The routed path barely improves, which is consistent with serial per-request
OpenSubdiv topology/refiner construction dominating the measured workload.
The guarded route is correct but is not yet a performance replacement for the
direct regular evaluator.

## Historical ownership boundary

At the PR #105 baseline, the active route constructed OpenSubdiv
topology/refiner state during every regular-row request. The later cache work
therefore had to answer, before implementation:

- Which mesh object owns topology, stencil tables, and source-id remapping?
- Which topology mutations invalidate the cache?
- Which coordinate-only updates can safely reuse topology-derived rows?
- How are copies, moves, destruction, and concurrent serial/OpenMP evaluation
  handled without shared mutable backend state?
- How is direct fallback preserved for boundary, ghost, irregular,
  non-equivalent, and otherwise unsupported faces?

That evidence was reviewed before choosing the cache lifetime. This historical
section records the questions that PR #107 through PR #109 answered; it is not
the current uncached implementation state.

The cache ownership, fingerprint, invalidation, copy/move, and concurrency
contract is recorded in `docs/opensubdiv_regular_cache_readiness.md`. PR #108
accepted the test-only prototype. The separate production implementation and
its post-cache benchmark, now measuring 1.10x to 1.91x routed/direct, are
recorded in `docs/opensubdiv_regular_production_cache.md`.

## Completion

PR #109 installs the reviewed mesh-owned immutable row cache with exact
identity verification. Both regular area/volume and force evaluation reuse the
same published row table while coordinates change, and rebuild when topology
or the frozen sample plan changes. The corrected-head benchmark measures
`1.15x` to `1.95x` routed/direct instead of the uncached `4.02x` to `25.11x`.

The regular 12-control performance correction is complete. Default builds
remain OpenSubdiv-free, and boundary, ghost, irregular, unsupported, and
non-equivalent faces retain their existing fallback. Irregular or
broader-valence routing requires a separate scientific and implementation
plan.
