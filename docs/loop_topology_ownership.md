# Loop topology ownership index

## Scope

This package adds an observational index over the complete face list. It reads
only `faces[*].adjacentVertices` and a declared vertex count. Coordinates and
rectangular grid indices are not inputs. Existing mesh setup and adjacency
routines are unchanged.

L7 is a mandatory prerequisite of WP9 because that later lane presumes owned
edge incidence and a validated topology representation. L7 is independent of
D9a, D9b, and the B packages. This package supplies no topology mutation,
transaction, epoch, evaluator wiring, formula change, or cost claim.

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

The test-only friend accessor can omit one check at a time. Tests demonstrate
that every omission admits a mesh rejected by the ordinary entry point; callers
cannot select that path.

## Evidence contract

The single focused test file checks the five declared closed fixture families,
the metadata-described before/after family, all listed rejection classes,
deterministic byte ordering, coordinate independence, and validation-check
sensitivity. The largest checked-in fixture is also used for a plain
construction-time measurement with no acceptance threshold or comparison.

Default builds require neither OpenSubdiv nor CUDA for this index. Sanitizer,
default-suite, readiness-script, coverage-copy, and whitespace evidence are
recorded at the package gate; independent T2 review remains required.
