# Irregular Fixture Discovery Report

This is a docs/scripts-only inventory for representative irregular fixture
discovery. It does not change production C++ behavior, build files, dependency
policy, OpenSubdiv policy, force formulas, scatter order, routing, propagation,
checkpoint/output, or broader valence support.

The companion command is:

```text
python3 scripts/inventory_irregular_fixture_candidates.py --check
```

The command reads checked-in face/vertex CSV mesh fixtures, records
coordinate-only CSVs as skipped sources when face connectivity is unavailable,
and includes a generated closed icosahedron topology probe. The generated probe
is inert and exists only to prove that the inventory maps an all-valence-5
physical triangular mesh into the current `11 = 4+3+4` route bucket.

## Route Mapping

| Route | Inventory predicate | Current behavior |
| --- | --- | --- |
| Regular 12-control membrane force | Interior/non-ghost face whose three vertices all have valence 6. | Supported. |
| Supported positive-depth 11-control `4+3+4` route | Interior/non-ghost face whose three vertices all have valence 5. | Supported narrowly when `Param::subDivideTimes > 0`. |
| Zero-depth 11-control guard | Same 11-control candidate with zero subdivision depth. | Guarded unsupported. |
| Unsupported broader valence | Non-boundary face outside the current regular-12 and 11-control predicates. | Unsupported; regular fallback remains disabled. |
| OpenSubdiv-replacement gap | Unsupported physical irregular topology needing a future backend policy. | Not production. |

CSV fixtures do not serialize `Face::isGhost`. For the now-approved
`data/example` physical mesh, the companion `example.params` declares periodic
boundaries and the row-major face topology resolves to `nFaceX=40` and
`nFaceY=46`. The inventory therefore applies the exact face-index policy from
`Mesh::determine_ghost_vertices_faces()`. A production-setup C++ test verifies
the same classification. Other CSV inputs continue to report ghost status as
unavailable unless they carry an equally explicit reviewed contract.

## Current Inventory Snapshot

The command discovers the negative `data/example` physical fixture and the
approved narrow positive stand-in under `data/fixtures/closed_valence5`.
For `data/example`:

- 1,927 vertices and 3,680 faces.
- Edge incidence counts: 172 boundary edges and 5,434 two-face edges.
- Production ghost classification: 960 ghost faces and 2,720 physical faces.
- Every physical face has the regular 12-control one-ring.
- All 336 mixed-valence faces are in the periodic ghost band; none is an
  eligible physical irregular face.
- No checked-in physical 11-control candidate is present because no physical
  face has an all-valence-5 interior one-ring predicate.

The topology-only mixed-valence leads such as `4/6/6` and `5/6/6` are now
resolved: production setup classifies all of them as ghosts. The approved mesh
is a useful negative physical fixture, but it cannot validate the supported
11-control route or any broader-valence OpenSubdiv route.

Coordinate-only Gag and shape CSVs under `data/` are reported as skipped
sources because they do not include face connectivity. They cannot establish
face one-ring size, boundary status, ghost status, or route eligibility by
themselves.

The generated `closed_icosahedron_valence5` probe reports:

- 12 vertices and 20 faces.
- All 30 edges have two incident faces.
- All generated faces are non-ghost.
- All 20 faces derive an 11-control one-ring and map to the supported
  positive-depth `11 = 4+3+4` route.
- The same 20 faces also map to the zero-depth guard when
  `Param::subDivideTimes <= 0`.

The user-approved narrow scientific stand-in is now checked in as the same
coordinates/connectivity under `data/fixtures/closed_valence5`. Production
setup confirms 20 physical 11-control faces and executable serial/OpenMP
evidence is recorded separately. This approval does not approve
broader-valence or OpenSubdiv irregular routing.

## Resulting Gap Status

The representative fixture decisions are now resolved for the negative
physical fixture and the narrow positive stand-in:

- The repo now has an inert command and report for discovering candidate
  irregular fixtures.
- The approved checked-in mesh provides explicit production ghost status and
  proves that it has no physical irregular face.
- The serialized closed valence-5 stand-in supplies the approved positive
  11-control fixture contract. Broader-valence fixture requirements remain
  open and separate.

The serial/OpenMP tolerance policy, broader valence policy, and OpenSubdiv
replacement criteria remain separate lanes.
