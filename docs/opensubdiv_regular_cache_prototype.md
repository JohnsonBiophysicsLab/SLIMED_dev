# Experimental OpenSubdiv Regular Cache Prototype

This lane implements the PR #107 cache contract only in a standalone,
OpenSubdiv-gated C++ experiment. It does not add cache ownership to `Mesh`,
change production routing, or alter default build/dependency behavior.

## Prototype boundary

`experiments/opensubdiv_regular_cache_prototype.cpp` wraps the existing guarded
regular row builder in a mesh-local experimental cache. The cache stores an
immutable backend-neutral final row table. Its fingerprint includes current
topology and source order, face eligibility, frozen sample/reference rows,
evaluator options, precision/tolerance policy, OpenSubdiv version, and a schema
version. Vertex coordinates are intentionally excluded.

The harness proves:

- one build for repeated unchanged evaluations;
- two repeated area/force helper evaluations with that single build;
- coordinate-only reuse after mutating a non-ghost source used by an eligible
  face, with a confirmed observable change and fresh cached-versus-direct
  comparison;
- misses after direct one-ring, adjacent-topology, face-index, boundary/ghost
  eligibility, quadrature, frozen-reference-row, and coherent sample-plan
  mutation;
- copy-empty and matching move-transfer behavior;
- isolation between two meshes;
- one publisher for concurrent readers;
- readers resumed after a serialized mutation of an already-populated cache
  observe exactly one rebuilt table;
- runtime opt-out ignores a populated cache and preserves direct semantics;
- unsupported-face fallback remains empty; and
- cached rows retain the frozen regular-row tolerance.

The observable comparison calls the same regular area/volume and
`element_energy_force_regular` helpers used by production, performs the
`Face::oneRingVertices` scatter, and compares total/constraint/bending energy,
force components, normals, area, legacy volume, and mean curvature against the
direct regular rows.

Topology or sample-plan mutation is serialized against lookup/build/readers in
this prototype. Concurrent public-container mutation remains unsupported.

## Running

Without a dependency, the wrapper skips cleanly:

```sh
scripts/run_opensubdiv_regular_cache_prototype.sh
```

With an ABI-compatible OpenSubdiv prefix:

```sh
OPENSUBDIV_ROOT=/path/to/opensubdiv \
  scripts/run_opensubdiv_regular_cache_prototype.sh --require-opensubdiv
```

The JSON report is proof-only and carries `not_production_cache:true`.

## Local proof result

At merge base `e6e8ed7`, the harness passed with an ABI-matched GCC 15 /
OpenSubdiv 3.7.0 prefix. It built one table for unchanged and coordinate-only
evaluations, detected topology and sample-plan mutations, preserved copy/move
and concurrent-reader rules, ignored a populated cache after runtime opt-out,
and matched the frozen regular rows to `2.7755575615628914e-16`.

The PR #106 benchmark matrix was repeated with three measured runs after one
warmup. Routed/direct ratios were `3.97x` and `5.01x` at `lFace=12.5`, `6.98x`
and `13.48x` at `lFace=7.5`, and `10.51x` and `25.54x` at `lFace=5.0` for one
and four threads respectively. This prototype is not installed in that
executable, so the rerun intentionally confirms the unchanged pre-cache
production cost rather than claiming a speedup.

## Remaining gate

The prototype and benchmark rerun pass. Production ownership, invalidation,
and call-site reuse still require a separate reviewer/user-gated production
PR. Broader-valence routing remains out of scope.
