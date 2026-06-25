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

CSV fixtures do not serialize `Face::isGhost`, so the checked-in CSV inventory
reports ghost status as unavailable and uses topology boundary status only.
Generated probes can report non-ghost status directly.

## Current Inventory Snapshot

`data/example/vertices_flat.csv + data/example/faces_flat.csv` is the only
checked-in triangulated mesh fixture discovered by the command:

- 1,927 vertices and 3,680 faces.
- Edge incidence counts: 172 boundary edges and 5,434 two-face edges.
- Derived one-ring sizes: 3,344 regular 12-control faces and 336 unavailable
  faces.
- Route counts: 3,344 regular faces, 170 boundary-excluded faces, and 166
  non-boundary faces outside the current regular/11-control predicates.
- No checked-in physical 11-control candidate is currently discoverable from
  serialized mesh CSVs because no face has an all-valence-5 interior one-ring
  predicate.

The non-boundary unsupported examples in `data/example` occur where topology
shows mixed valence triplets such as `4/6/6` or `5/6/6`. Because ghost flags
are not serialized, these are evidence-discovery candidates only; promoting
them into production tests needs an approved fixture with explicit
boundary/ghost status and expected behavior.

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

This generated probe is not a production scientific fixture. It is a
topology-only sanity check that the discovery command can identify physical
11-control candidates when face connectivity exposes them.

## Resulting Gap Status

The representative fixture gap is narrowed but not closed:

- The repo now has an inert command and report for discovering candidate
  irregular fixtures.
- The checked-in triangulated mesh inventory currently provides regular
  12-control evidence and unsupported mixed-valence discovery leads, but no
  serialized physical 11-control fixture with explicit ghost status.
- A future fixture PR can use this command to verify that a proposed mesh
  includes non-ghost 11-control candidates before adding numerical expectations.

The serial/OpenMP tolerance policy, broader valence policy, and OpenSubdiv
replacement criteria remain separate lanes.
