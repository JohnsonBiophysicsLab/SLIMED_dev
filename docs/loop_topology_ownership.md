# Loop topology ownership index

## Scope

This package adds an observational index over the complete face list. It reads
only `faces[*].adjacentVertices` and a declared vertex count. Coordinates and
rectangular grid indices are not inputs. The ownership construction and mesh
adjacency routines are unchanged; the two mesh setup entry points now use one
internal topology invalidation seam in place of their former direct regular-row
cache invalidations.

L7 is a mandatory prerequisite of WP9 because that later lane presumes owned
edge incidence and a validated topology representation. L7 is independent of
D9a, D9b, and the B packages. This package supplies no topology mutation,
transaction, evaluator wiring, formula change, or cost claim.

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
existing regular-row cache, and advances the generation once. The only callers
are `setup_from_vertices_faces()` and `setup_flat()`, replacing the direct cache
invalidation previously present at the start of each entry point. Consequently,
each setup call advances once, while direct coordinate edits do not advance.
The seam is private so a caller cannot clear derived state or advance identity
without entering mesh setup.

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

## Evidence contract

The single focused test file checks the five declared closed fixture families,
the metadata-described before/after family, all listed rejection classes,
deterministic byte ordering, coordinate independence, and validation-check
sensitivity. It also checks zero initialization, exact one-step increments at
both setup entry points, coordinate stability, copy construction, deliberately
unavailable copy assignment, complete existing-key identity, exact fixture
ownership/diagnostics, and missed-bump sensitivity. The largest checked-in
fixture is also used for a plain construction-time measurement with no
acceptance threshold or comparison.

Default builds require neither OpenSubdiv nor CUDA for this index. Sanitizer,
default-suite, readiness-script, coverage-copy, and whitespace evidence are
recorded at the package gate; independent T2 review remains required.
