# Unsupported Broader-Valence Inventory

This is a docs/scripts/tests-only characterization of the current production
boundary. It does not enable broader-valence routing or change formulas,
scatter, OpenMP reduction, dependencies, checkpoint/output, or propagation.

## Current Production Shape

`Mesh::set_one_ring_vertices_sorted()` stores a 12-slot one-ring only when all
three face vertices have valence 6, and an 11-slot one-ring only when all three
have valence 5. A physical face with any other valence triplet keeps an empty
`Face::oneRingVertices` vector.

The area/volume switch and membrane force loop likewise have branches only for
12 and 11 slots. For an unsupported empty one-ring, current behavior is:

- no regular fallback is used;
- no explicit broader-valence preflight diagnostic is emitted;
- area and legacy volume are stored as zero;
- curvature energy and mean curvature retain initialized zero values; and
- no membrane force rows are scattered.

This silent zero contribution is the exact blocker. It is inventory evidence,
not an approved unsupported-topology policy.

## Generated Closed Topologies

`scripts/inventory_irregular_broader_valence.py` uses closed, two-face-edge
triangulations so boundary exclusion does not hide the production predicate.

| Topology | Face valence triplet | Faces | Stored one-ring size | Current diagnostic |
| --- | --- | ---: | ---: | --- |
| Tetrahedron | `3/3/3` | 4 | `0` | none |
| Octahedron | `4/4/4` | 8 | `0` | none |
| Triangular bipyramid | `3/4/4` | 6 | `0` | none |
| Pentagonal bipyramid | `4/4/5` | 10 | `0` | none |
| Hexagonal bipyramid | `4/4/6` | 12 | `0` | none |
| Heptagonal bipyramid | `4/4/7` | 14 | `0` | none |
| Nonagonal bipyramid | `4/4/9` | 18 | `0` | none |
| Approved valence-5 control | `5/5/5` | 20 | `11` | not applicable |

These generated cases characterize topology predicates only. They are not
scientifically approved broader-valence fixtures and do not establish an
OpenSubdiv ptex/sample/source-id or force-transpose contract.

## Next Gate

Before any broader-valence backend or physics work, production setup/evaluation
should fail loudly for a non-ghost, non-boundary face whose stored one-ring size
is neither 11 nor 12. That diagnostic change is production C++ behavior and
requires a separate reviewer/user-gated PR. It should preserve the approved
valence-5 route and all default dependency, formula, scatter, OpenMP,
checkpoint/output, and propagation behavior.
