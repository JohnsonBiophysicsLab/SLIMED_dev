# Valence-4 Source-Keyed Kernel Adapter Proof

This review-gated proof closes the adapter-design boundary identified by the
PR122 production-call boundary. PR124 moves that proven backend-neutral
boundary into `energy_force/Source_keyed_kernel_call` and calls the production
helper from this opt-in harness. It combines:

- the guarded `Valence4TopologySourceMapping` for the approved closed
  valence-4 octahedron;
- fresh proof-provided OpenSubdiv rows with shape
  `8 faces x 3 samples x 7 rows x 6 sources`; and
- the existing proof-local `fBend`, `fArea`, and `fVolume` face
  contributions.

The production helper API is backend-neutral. It accepts face identity, canonical
orientation, original source IDs, derivative rows, and source-keyed force
contributions. It has no OpenSubdiv type and does not accept or pad
`Face::oneRingVertices`.

`prepare_source_keyed_kernel_call(...)` validates the complete request before
returning an owned canonical result.
`accumulate_source_keyed_force_contributions(...)` returns a separately owned
source-keyed force table. Neither helper mutates its input, a `Mesh`, a
`Face`, vertex force storage, or production OpenMP buffers.

The production-shaped successor adds
`scatter_source_keyed_face_forces_to_component_buffer(...)` and
`reduce_source_keyed_force_component_buffers(...)`. These backend-neutral
helpers use the current `source * 9 + force-kind * 3 + axis` layout and reduce
caller-owned buffers in ascending buffer order. Complete validation and a
staged-before-publication update keep malformed input atomic. They do not inspect
OpenMP state or write `Vertex` force storage.

## Contract

Each face carries its own variable-cardinality source set. The adapter sorts
that set by original source ID, reorders uniquely keyed force columns into
that canonical order, and aggregates derivative-row entries by source ID.
Input row and force column order therefore has no semantic meaning.

Derivative rows may contain repeated source IDs because the existing SLIMED
row contract aggregates duplicate source contributions. The adapter sorts
each source's finite contributions before a `long double` sum so split and
reversed duplicates reduce deterministically. Topology mappings and force
inputs retain their unique-source contracts. The proof adapter rejects:

- out-of-range or duplicate topology/force source IDs;
- incomplete derivative-row source coverage;
- inconsistent row or force cardinality;
- nonfinite row or force data;
- canonical orientation or source-mapping drift;
- nonempty production one-rings; and
- drift between the duplicated mixed derivative rows.

The approved octahedron happens to have six sources per face. The API does not
encode six as a kernel cardinality; six is supplied by this proof fixture.

## Independent Oracle

The candidate adapter scatters all eight face-local force contributions by
their original source IDs. A separate fixed-source nested-array oracle looks
up every force column's source key and sums the proof contributions in
`face -> keyed source -> force kind -> axis` order. It never calls the adapter
scatter or reuses its destination indexing.

The harness reverses every derivative-row and force binding, then requires
the canonical adapted rows, force columns, scattered result, and independent
oracle result to match the baseline. It also splits one coefficient per row
into two reversed duplicate-key entries and requires the aggregated canonical
rows to remain identical.

The machine-readable report binds permutation invariance, duplicate-row
aggregation, exact source coverage, all malformed-input gates, finite data,
empty production one-rings, and maximum oracle/canonicalization deltas no
greater than `1e-12`.

## Boundary

The report states:

```text
proof_only: true
not_production_routing: true
production_route_enabled: false
actual_production_force_path_executed: false
production_kernel_call_helper_executed: true
production_one_rings_mutated: false
```

This proof does not install a production caller, mutate the mesh, populate
one-rings, change formulas or scatter, change OpenMP buffers/reductions, alter
default dependency/build behavior, or approve broader valence.

The helper consumes already-computed source-keyed force contributions.
Variable-cardinality scientific algebra and the guarded, default-off
scientific request are now separately reviewed production-neutral
boundaries. Production valence-4 route activation remains unapproved.

## Guarded Scientific Request Composition

The opt-in present-dependency proof passes the freshly generated OpenSubdiv
`8 x 3 x 7 x 6` row tensor into
`evaluate_guarded_valence4_face_loop_scientific_request(...)`. The request
uses the approved octahedron's production `Mesh` coordinate storage populated
with the established asymmetric proof coordinates and invokes the existing
variable-cardinality scientific algebra. It returns caller-owned face
observables and source-keyed force totals.

The composition passes only when its face observables match the established
proof-local algebra, its source-force totals match the independent
source-keyed aggregation, a default-off request is rejected, and all
public face and vertex fields remain exactly unchanged. The binding snapshot
compares complete matrices, energy and force families, coordinates, normals,
topology vectors and flags, and full one-ring contents. Adversarial mutations
to the previously omitted geometry, energy, coordinate, force, and one-ring
categories must all be detected before the report can pass.
The fresh scientific-request output is also scattered through the
production-shaped component helper and reduced back to source-keyed force
families. That result must match the independent source-force reference under
`1e-12`.
`Face::oneRingVertices` stays empty and the report continues to require
`production_route_enabled: false`. This is evidence for the provider/request
and caller-owned scatter-buffer boundaries, not route activation.

## Run

Dependency-absent behavior is a clean skip:

```bash
scripts/run_irregular_valence4_source_keyed_kernel_adapter.sh --json
```

Present-dependency proof:

```bash
OPENSUBDIV_ROOT=/tmp/slimed-opensubdiv-install \
OPENSUBDIV_CXXFLAGS='-arch arm64' \
scripts/run_irregular_valence4_source_keyed_kernel_adapter.sh \
  --json --require-opensubdiv
```

Inventory:

```bash
python3 scripts/inventory_irregular_valence4_source_keyed_kernel_adapter.py \
  --check
```
