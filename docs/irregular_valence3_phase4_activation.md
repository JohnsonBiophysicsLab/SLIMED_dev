# Valence-3 OpenSubdiv Phase-4 Activation

Phase 4 installs the reviewed exact-tetrahedron transaction in
`Mesh::Compute_Energy_And_Force()` behind the exact runtime token:

```text
SLIMED_USE_OPENSUBDIV_VALENCE3=1
```

The gate is independent from the Phase-3 integration token. With no production
token, the tetrahedron retains the existing unsupported-topology diagnostic.
With a dependency-disabled build, an exact production request rejects before
the first Mesh write.

## Route selection

The default evaluator reads all three extraordinary route requests before any
geometry or force mutation. It counts Valence 3, 4, and 5 requests and rejects
when more than one is active. A single Valence-3 request calls
`evaluate_guarded_valence3_opensubdiv_production_route()`, which delegates to
the exact reviewed Phase-3 transaction and marks the returned result as the
production/default-evaluator Phase-4 route only after acceptance.

The accepted scope remains:

- OpenSubdiv 3.7.0;
- the exact outward-oriented four-source tetrahedron;
- adaptive isolation level 5;
- the ordered three-sample rule with weights 1/3; and
- the full-divergence volume functional selected before activation.

Mixed 3/4/5 topology, topology or sample drift, missing OpenSubdiv support,
and conflicting extraordinary gates reject atomically.

## Immutable row cache

The provider caches only a fully validated row result. Its identity is fixed
by the provider contract: exact topology and orientation, source boundary,
sample plan, Loop options, isolation level, and compile-time OpenSubdiv
version. Coordinates are not part of the cache. Exact topology preflight runs
before every lookup, and cache insertion occurs only after every row/Ptex/
invariant check succeeds.

The activation proof requires the first accepted call to populate the cache
and a later production call to report a hit. One local WSL run measured 1472
microseconds for the uncached guarded transaction and 633 microseconds for the
cached production transaction. These timings are diagnostic, not performance
thresholds.

## Verification contract

The real production caller is exercised twice at each of 1, 2, and 4 OpenMP
threads. Non-timing output is compared under the fixed 1e-10 postcondition
envelope. The measured maximum cross-thread difference was
`1.4210854715202004e-14`; repeated calls at each fixed count were identical in
the reviewed run.

The proof also requires:

- nonzero volume energy and force with the conjugate full-divergence volume;
- exact dry-run/post-publication agreement under 1e-10;
- atomic mixed-topology and three-way route-conflict rejection;
- unchanged one-rings and finite output-visible state;
- energy CSV, per-face CSV, and V2 checkpoint round-trip coverage; and
- no Valence-4, Valence-5, or CUDA source changes.

The runtime token is the rollback switch. Unsetting it returns immediately to
the prior fail-loud unsupported-tetrahedron behavior.
