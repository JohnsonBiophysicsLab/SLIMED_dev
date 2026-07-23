# Unsupported Broader-Valence Inventory

This document records the production guard added after the topology inventory.
It does not enable broader-valence routing or change formulas, scatter, OpenMP
reduction, dependencies, checkpoint/output, or propagation.

## Current Production Shape

`Mesh::set_one_ring_vertices_sorted()` stores a 12-slot one-ring only when all
three face vertices have valence 6, and an 11-slot one-ring only when all three
have valence 5. A physical face with any other valence triplet keeps an empty
`Face::oneRingVertices` vector.

The area/volume switch and membrane force loop likewise have branches only for
12 and 11 slots. Before geometry evaluation, a topologically interior,
non-ghost face whose stored one-ring size is neither 11 nor 12 now fails with
an explicit runtime diagnostic. Faces incident to an open mesh boundary remain
on the legacy boundary path even though fixed-boundary setup does not populate
the deprecated `Face::isBoundary` flag. Therefore current behavior is:

- no regular fallback is used;
- area and legacy volume are not mutated;
- curvature energy, mean curvature, and membrane force rows are not evaluated;
  and
- broader-valence routing remains disabled.

This closes the silent-zero blocker. It is an unsupported-topology guard, not
an approval of broader-valence physics or routing.

## Generated Closed Topologies

`scripts/inventory_irregular_broader_valence.py` uses closed, two-face-edge
triangulations so boundary exclusion does not hide the production predicate.

| Topology | Face valence triplet | Faces | Stored one-ring size | Current diagnostic |
| --- | --- | ---: | ---: | --- |
| Tetrahedron | `3/3/3` | 4 | `0` | fail-loud runtime error |
| Octahedron | `4/4/4` | 8 | `0` | fail-loud runtime error |
| Triangular bipyramid | `3/4/4` | 6 | `0` | fail-loud runtime error |
| Pentagonal bipyramid | `4/4/5` | 10 | `0` | fail-loud runtime error |
| Hexagonal bipyramid | `4/4/6` | 12 | `0` | fail-loud runtime error |
| Heptagonal bipyramid | `4/4/7` | 14 | `0` | fail-loud runtime error |
| Nonagonal bipyramid | `4/4/9` | 18 | `0` | fail-loud runtime error |
| Approved valence-5 control | `5/5/5` | 20 | `11` | not applicable |

These generated cases characterize topology predicates only. They are not
scientifically approved broader-valence fixtures and do not establish an
OpenSubdiv ptex/sample/source-id or force-transpose contract.

## Serialized Valence-4 Candidate

The regular octahedron is now also serialized under the clearly candidate-only
path `data/fixtures/candidates/closed_valence4_octahedron`. Its candidate
metadata records coordinates, outward-oriented connectivity, exact edge
length, circumradius, face and total polyhedral area, and signed enclosed
polyhedral volume. These are straight-sided input-polyhedron values, not
SLIMED outputs.
The inert companion inventory is:

```text
python3 scripts/inventory_irregular_valence4_fixture_candidate.py --check
```

Production setup coverage confirms that all eight faces are physical, have
valence triplet `4/4/4`, and retain empty one-rings. The PR114 guard rejects the
first unsupported face before any seeded area or volume is mutated.

This candidate packet remains a candidate, not a scientifically approved
fixture. Generic scientific approval is still absent. It is now
approved narrowly as a stand-in for the proof-only mapping/sample/transpose
lane in `docs/irregular_valence4_opensubdiv_mapping_proof.md`. That report
freezes the 24 OpenSubdiv samples, dense source rows, Ptex identities, and a
linear transpose without approving membrane/backend outputs. Broader-valence
routing remains disabled.

## Remaining Gate

Any broader-valence backend or physics work still needs generic scientific
approval, expected membrane geometry/force outputs, production scatter and
OpenMP evidence, and an explicit route contract. The regular-octahedron proof
closes only the mechanical mapping/sample/transpose evidence slice. The guard
must remain active until separate production and scientific review approves a
route.
