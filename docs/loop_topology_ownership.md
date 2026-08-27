# Loop topology ownership and transaction

## Scope

The L7a package added an observational index over the complete face list. It
reads only `faces[*].adjacentVertices` and a declared vertex count. Coordinates
and rectangular grid indices are not inputs. L7b added one monotonic Mesh
topology generation and internal invalidation seam. L7c adds a deliberately
inactive fixed-cardinality transaction that stages and validates candidate face
connectivity, rebuilds connectivity-derived adjacency, and either commits it or
leaves the live Mesh unchanged.

L7 is a mandatory prerequisite of WP9 because that later lane presumes owned
edge incidence and a validated topology representation. L7 is independent of
D9a, D9b, and the B packages. L7c supplies transaction infrastructure, not an
edge-flip algorithm, candidate selector, runtime route, evaluator wiring,
formula change, or cost claim.

## Ownership and ordering

`LoopTopologyOwnershipIndex::build()` stages a unique undirected-edge table in
lexicographic `(min(u,v), max(u,v))` order. Every accepted edge records its two
source face IDs and the corresponding oriented directions. Face IDs and vertex
IDs remain SLIMED integer IDs.

For each vertex, incident faces are linked through oppositely oriented shared
edges. Following the incoming edge of each oriented triangle gives the
counter-clockwise successor. The cycle starts at the smallest incident face ID,
making the representation deterministic without consulting coordinates.

## Fail-closed validation

The build result always contains a reason code and diagnostics. Ownership is
present only after the complete staged representation passes the approved D2
scope: triangular, closed, connected, consistently oriented two-manifold input
with every declared vertex used. Boundaries and holes therefore fail before an
ownership value is returned.

Distinct reason codes cover non-triangles, out-of-range vertex IDs, repeated
vertices, duplicate faces, unused vertices, one-face edges, edges with more
than two incident faces, shared-edge orientation conflicts, invalid vertex-link
cycles, and disconnected meshes. Diagnostics retain deterministic edge
incidence counts, both vertex-link degree and connectivity failures, component
and boundary-loop counts, Euler characteristic, and per-vertex valence.

`build()` is the only entry point, and there is no second, less-validated one:
the type exposes no private builder, no validation-check mask, and no friend
declaration, so no translation unit can obtain ownership that skipped a check.
An earlier revision did carry a mask builder reachable through a friend
declared but not defined in this header; because that name was injected at
global scope, any translation unit could claim it and publish unvalidated
ownership, so both the mask and the friend were removed rather than hidden.

Check sensitivity is instead demonstrated through the public entry point.
`build()` applies its checks in a fixed precedence order and returns the first
matching reason code, so a fixture whose earliest violated check is X must
produce X's own code; deleting X changes the observed code or accepts the mesh
outright. Each fixture is additionally shown to leave every strictly earlier
signature clean, which is what makes X decisive. Later signatures are left
unconstrained deliberately: a fixture may violate a later check too, and
precedence already settles which one rejected it. All ten checks are verified
load-bearing this way.

Note one deliberate asymmetry the tests rely on: `edge_incidence_counts` is raw
evidence and counts every incident face, while the edge-incidence check first
attributes duplicate faces away. The two therefore disagree for a
duplicate-face mesh, which is why sensitivity is argued from precedence rather
than by re-deriving the attribution rule in the test.

All names live in `namespace slimed::loop_topology`, matching the repository's
`slimed::<lane>` convention, so nothing in this header occupies global scope.

## Topology generation and identity

`Mesh` starts with topology generation zero. Its private
`invalidate_topology_derived_state()` seam rejects integer overflow, clears the
existing regular-row cache, and advances the generation once. Its reviewed
callers are `setup_from_vertices_faces()`, `setup_flat()`, and the L7c
transaction commit, replacing the direct cache invalidation previously present
at the start of each setup entry point. Consequently, each setup or successful
transaction commit advances once, while direct coordinate edits do not advance.
The seam is private so a caller cannot clear derived state or advance identity
without entering mesh setup or the one reviewed topology transaction. A fully
qualified friend names the transaction class whose complete definition is
included before `Mesh` is declared; there is no unclaimed global or qualified
friend name and no generic cache-reset capability. A compile-negative test
confirms that a translation unit including only `Mesh.hpp` cannot redefine the
friend type to acquire private access.

Implicit copy construction preserves the generation. `Mesh` remains
non-copy-assignable because it owns a `Param&`; L7b does not add assignment
semantics or change how that reference is bound.

`slimed::loop_limit::LoopTopologyKey` remains the sole row identity; L7b adds no
second key. Its existing `topologyEpoch` field accepts `Mesh::topology_generation()`
alongside its existing oriented connectivity, source count, boundary/ghost/hole
policy, evaluator API, approximation levels, cache mode, library version, and
quadrature policy fields. Coordinates remain absent. Focused tests compose the
Mesh value into that existing key and show that every listed field changes the
identity, that coordinate edits do not, and that an equal-connectivity rebuild
is distinguishable only by the advanced epoch. This package does not connect a
new runtime consumer to that key.

## Atomic fixed-cardinality transaction

`LoopTopologyTransaction` snapshots the source generation, vertex and face
cardinality, and exact oriented face rows when it is constructed. `stage()`
accepts only the same number of faces and rejects an exact no-op. It builds
temporary `Face` rows and invokes the public fail-closed ownership validator;
an invalid candidate retains that validator's distinct reason code and never
writes the Mesh.

For an accepted candidate, staging constructs every connectivity-owned vector
before commit:

- each face gets exactly three neighboring face IDs, in its local oriented-edge
  order;
- each vertex gets the ownership index's counter-clockwise incident-face cycle;
- vertex neighbors are aligned with that cycle by taking the outgoing vertex of
  each incident oriented face; and
- evaluator-specific `Face::oneRingVertices` rows are staged empty so rows from
  the previous topology cannot survive under a new epoch.

Staging and explicit rollback only own temporary vectors. They therefore leave
the live connectivity, derived vectors, topology generation, coordinates,
labels, geometry, energy, and force objects unchanged. A rejected stage is
finalized fail-closed rather than being partially repaired or retried through a
less-validated path.

Before commit, the transaction rechecks generation, both cardinalities, and
the exact source face rows. This catches both a competing accepted transaction
and direct public face-connectivity drift that did not advance the epoch. The
commit then checks generation overflow and calls the private invalidation seam
once. Every subsequent live write is a `std::vector<int>::swap`, statically
required to be `noexcept`; the installed connectivity and all derived vectors
were already built. Thus under the required exclusive-Mesh-access precondition,
an exception cannot expose a partial topology: invalidation failure precedes
all swaps, while nothing after successful invalidation can throw.

The transaction is intentionally single-use and non-copyable. `commit()` and
`rollback()` require a successfully staged candidate, and either operation
finalizes it. Structured transaction reasons distinguish state-machine misuse,
fixed-cardinality/no-op policy rejection, nested topology rejection, derived
rebuild failure, stale generation/cardinality/connectivity, overflow, and
invalidation failure.

This package does not serialize nonparticipating concurrent readers; callers
must hold exclusive access to the Mesh. It preserves non-connectivity fields by
retaining the existing `Vertex` and `Face` objects, but that mechanical face-ID
retention is not an approved physical insertion/material/layer label transfer
policy. One-rings are cleared rather than evaluator-rebuilt, so a committed
transaction is not evaluator- or science-ready. Topology-aware checkpoint and
restart, L7e periodic/ghost/boundary/material/label policy, L7f optimizer and
dynamics consequences, Gate-C evaluator coverage, Gate-D science continuity,
and production flip activation all remain separately deferred.

## L7d restart checkpoint write interlock

The V1 and V2 restart formats do not store oriented face connectivity. L7d
therefore does not change either format or claim topology-aware restart.
Instead, `Mesh` records the topology generation installed by the last setup
that completed successfully. Both setup entry points refresh that marker only
after their rebuild work completes. A committed L7c transaction advances the
live topology generation through the existing invalidation seam but does not
refresh the setup marker.

The restart writer compares those generations before it opens the temporary
checkpoint file. A mismatch fails the write and leaves any existing destination
unchanged. The transaction has no production caller, so every existing workload
continues to write the same `SLIMED_RESTART_V2` byte schema. The interlock makes
the L7-before-WP9 ordering executable: a future caller cannot commit a topology
transaction and then emit a connectivity-blind checkpoint through the current
writer.

This is deliberately negative evidence, not completion of topology-aware
restart. It does **not** discharge L7 item 5 in the Bfr plan or Gate E in the
adaptive-flipping feasibility record. L7 closes with that open blocker recorded;
WP9 remains blocked on a separate C4-reviewed, explicitly user-approved D13
decision package for the connectivity payload, V2-as-legacy-read behavior, and
a tag bump for every schema change. L7d neither creates nor approves that
schema.

## Evidence contract

The ownership test checks the five declared closed fixture families,
the metadata-described before/after family, all listed rejection classes,
deterministic byte ordering, coordinate independence, and validation-check
sensitivity. It also checks zero initialization, exact one-step increments at
both setup entry points, coordinate stability, copy construction, deliberately
unavailable copy assignment, complete existing-key identity, exact fixture
ownership/diagnostics, and missed-bump sensitivity. The transaction test uses
the authoritative single-flip family to check exact stage/rollback and
validator-rejection nonmutation, fixed-cardinality and no-op policy, one-step
commit generation, connectivity-derived face and vertex adjacency, cleared
evaluator one-rings, non-connectivity retention, competing epochs, unversioned
source drift, cardinality drift, state-machine finalization, and stable reason
names. The largest checked-in fixture is also used for a plain construction-time
measurement with no acceptance threshold or comparison.

Both regular-cache inventories now admit exactly one third seam caller: the
namespaced transaction's unique `commit() noexcept` scope. Their focused
mutations reject missing, duplicate, conditional, unreachable, renamed,
macro-shadowed, include-injected, access-widened, or additional callers while
retaining the all-source cache/generation scan.

Default builds require neither OpenSubdiv nor CUDA for this package. Sanitizer,
default-suite, readiness-script, coverage-copy, and whitespace evidence are
recorded at the package gate; independent T2 review remains required.
