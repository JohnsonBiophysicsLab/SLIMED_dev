# Production regular OpenSubdiv row cache

This lane installs the PR #108 cache contract in the guarded regular
OpenSubdiv production route. It changes production C++ ownership and is
therefore reviewer/user-gated. It does not change route eligibility, numerical
formulas, scatter order, OpenMP reductions, default dependency behavior,
checkpoint/output behavior, propagation, or broader-valence support.

## Ownership and publication

Each `Mesh` owns a backend-neutral `RegularLimitSurfaceRowCache`. The cache
publishes an immutable shared table indexed exactly like `Mesh::faces`.
OpenSubdiv objects remain local to table construction and never enter the
cache type or public production data.

Both regular area/volume evaluation and membrane force accumulation acquire
the same immutable table. A mutex permits one builder/publisher for a
fingerprint; readers retain shared ownership while serial or OpenMP evaluation
uses the table.

The cache member's copy constructor starts empty. Its move constructor
transfers the immutable table, fingerprint, and counters. A fully populated
`Mesh` is not copied in the acceptance test because existing nullable
`Matrix` members make that pre-existing operation unsafe; the cache adds no
shared backend state to it. Moving a populated mesh is covered directly.

## Fingerprint and invalidation

Lookup recomputes a fingerprint from:

- the cache schema, OpenSubdiv version, Loop scheme, boundary option,
  refinement depth, derivative options, row precision, and parity tolerance;
- vertex and face counts, face indices, triangular source order,
  `Face::oneRingVertices` source order, and boundary/ghost flags;
- `VWU`, quadrature coefficients, and frozen regular reference rows.

Coordinates are intentionally excluded, so propagation-only coordinate
updates reuse the table. `setup_flat()` and
`setup_from_vertices_faces()` explicitly clear the published table.
Public topology or sample-plan mutation is caught by the next fingerprint
comparison. Such mutation must remain serialized against lookup and readers.

Runtime opt-out returns before fingerprinting, lookup, reuse, or construction,
even when a prior opted-in evaluation populated the cache. Builds without
`USE_OPENSUBDIV_REGULAR=1` remain OpenSubdiv-free and preserve the existing
loud failure when runtime opt-in is requested.

## Acceptance evidence

The OpenSubdiv-enabled characterization covers:

- one build across area, force, repeated evaluation, and coordinate updates;
- topology and sample-plan misses;
- setup invalidation with a monotonically increasing build count;
- empty cache state on copy construction and populated-cache move transfer;
- eight concurrent readers with one publisher;
- runtime opt-out bypass of a populated cache;
- existing full direct-versus-routed geometry, energy, force, normal, area,
  and legacy-volume parity.

The dependency-free source inventory is:

```console
python3 scripts/inventory_opensubdiv_regular_production_cache.py --check
```

## Performance recheck

The PR #106 benchmark matrix was repeated with the same deterministic fixture,
one warmup, three measured runs, and the same executable for direct and routed
modes.

| `lFace` | Threads | Direct (s) | Routed (s) | Routed/direct |
|---:|---:|---:|---:|---:|
| 12.5 | 1 | 0.0711 | 0.0786 | 1.10x |
| 12.5 | 4 | 0.0505 | 0.0617 | 1.22x |
| 7.5 | 1 | 0.4118 | 0.5049 | 1.23x |
| 7.5 | 4 | 0.1952 | 0.2889 | 1.48x |
| 5.0 | 1 | 1.3236 | 1.7989 | 1.36x |
| 5.0 | 4 | 0.5188 | 0.9884 | 1.91x |

The uncached PR #106 baseline ranged from 4.02x to 25.11x. These local timing
results are performance characterization, not scientific acceptance
thresholds.

## Remaining boundaries

Boundary, ghost, irregular, unsupported, and non-equivalent faces retain
their existing direct or subdivision fallback. This lane does not add a
default OpenSubdiv dependency, broader-valence routing, or any production
formula, scatter, reduction, checkpoint, output, or propagation change.
