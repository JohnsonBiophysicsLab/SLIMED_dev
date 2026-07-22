# OpenSubdiv regular route cache readiness

This document defines the evidence and ownership contract required before the
guarded regular OpenSubdiv route may cache topology-derived rows. It is a
design/readiness artifact only. It does not add a cache, change the active
route, alter default dependency behavior, or expand supported topology.

## Why a cache is the next lane

The post-activation benchmark in
`docs/opensubdiv_regular_route_performance.md` measures the guarded route at
roughly 4x to 25x the direct path on the recorded fixture matrix. The current
implementation calls `build_opensubdiv_regular_shape_functions_by_face()`
from both area/volume evaluation and force accumulation. Each call creates and
adaptively refines an OpenSubdiv topology refiner, then creates per-face limit
stencil tables.

The resulting regular row matrices depend on mesh topology, face/source-id
order, eligibility flags, and the frozen sample plan. They do not depend on
current vertex coordinates. Coordinate-only propagation can therefore reuse
an already validated row table, but topology or sample-plan drift cannot.

## Candidate cache unit

The first prototype should cache the final backend-neutral row table rather
than expose or retain OpenSubdiv objects:

- outer index compatible with `Mesh::faces`;
- three samples for each eligible regular face;
- seven derivative rows by twelve original SLIMED source ids;
- eligibility and equivalence result for each face;
- a topology/sample-plan fingerprint and a monotonically increasing build id.

The row table must be immutable after publication. Boundary, ghost, irregular,
unsupported, and non-equivalent faces retain empty entries so their existing
direct or subdivision path remains active.

## Ownership decision

The preferred production owner is the mesh instance whose topology the rows
describe, behind a backend-neutral or opaque evaluator boundary. A process
global map keyed by `Mesh*` is rejected because pointer lifetime, address
reuse, destruction, and concurrent meshes cannot be made reliable by the
current API.

Before adding a member to `Mesh`, a prototype must settle copy and move
behavior. The conservative contract is:

- a copied mesh starts with an empty cache;
- a moved mesh may transfer an immutable cache only with its matching topology
  fingerprint, otherwise it starts empty;
- destruction releases all cache state without a global registry;
- `DynamicMesh` follows the same base-mesh ownership rules.

Because `Mesh::vertices` and `Mesh::faces` are currently public, invalidation
hooks alone are insufficient. Cache lookup must recompute and compare a
topology/sample-plan fingerprint until direct container mutation is removed or
encapsulated.

## Cache key and invalidation

The fingerprint must include:

- vertex count, face count, `Face::index`, and triangular
  `Face::adjacentVertices` order;
- `Face::oneRingVertices` source-id order;
- boundary and ghost eligibility flags;
- the frozen `VWU` sample coordinates, quadrature coefficient values/order,
  and regular reference row values and dimensions;
- Loop scheme, boundary interpolation, refinement depth, derivative options,
  row precision, equivalence tolerance, OpenSubdiv version, and a cache schema
  version.

The fingerprint must not include vertex coordinates. Coordinate changes are
cache hits. `setup_flat()`, `setup_from_vertices_faces()`, direct topology
container mutation, one-ring reorder, boundary/ghost reclassification, or
sample-plan changes must produce a cache miss and rebuild before publication.

## Concurrency contract

- Published row tables are immutable and may be read concurrently.
- At most one build for a fingerprint may publish; competing readers either
  wait for that build or use an already published matching table.
- Fingerprinting detects public topology or sample-plan mutation only between
  evaluations. Mutation of `Mesh::vertices`, `Mesh::faces`, one-ring state, or
  sample-plan inputs must be serialized against cache lookup, construction,
  publication, and readers; the cache does not make concurrent container
  mutation safe.
- No OpenMP worker mutates shared row matrices, topology state, diagnostics, or
  fallback state.
- Build counters and diagnostics must be synchronized and must not affect
  numerical accumulation order.
- Runtime opt-out bypasses cache lookup, reuse, and construction, including any
  table populated by an earlier opted-in evaluation, and preserves the current
  direct regular semantics. Default builds remain OpenSubdiv-free.

## Prototype acceptance gates

A non-production prototype must prove all of the following before a production
cache PR is proposed:

1. Two consecutive area/force evaluations of unchanged topology perform one
   row-table build and preserve all current parity channels.
2. Coordinate-only updates hit the cache and retain energy, forces, normals,
   area, legacy volume, and mean-curvature parity.
3. Every topology/sample-plan mutation listed above causes a miss; direct
   public-container mutation is detected by the fingerprint.
4. Copy, move, destruction, two simultaneous meshes, and concurrent readers do
   not share stale or mutable backend state. A serialized mutation/read test
   confirms that mutation produces a miss before readers resume; concurrent
   public-container mutation is explicitly unsupported.
5. Runtime opt-out ignores any previously populated table and preserves direct
   semantics; unsupported-face fallback, dependency-absent builds, and current
   serial/OpenMP reduction behavior remain unchanged.
6. The active regular route is benchmarked again with the same harness and
   fixture matrix used for the PR #106 baseline.

## Explicitly out of scope

This readiness lane does not approve production cache ownership, public
signatures, default OpenSubdiv linkage, broader-valence routing, formula or
scatter changes, OpenMP scheduling/reductions, checkpoint/output behavior, or
propagation changes. The next implementation should be an experimental or
test-only cache prototype. A production cache remains a separate reviewer and
user-gated PR.

The standalone proof in `docs/opensubdiv_regular_cache_prototype.md` satisfied
these gates in PR #108. Production cache ownership is implemented separately
and remains reviewer/user-gated.

## Inventory

Run the dependency-free source inventory with:

```console
python3 scripts/inventory_opensubdiv_regular_cache_readiness.py --check
```
