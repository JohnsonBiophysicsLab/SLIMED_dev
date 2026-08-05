# Valence-3 Phase-5 Triangular-Bipyramid Candidate

Phase 5 starts with a second closed, non-isomorphic Valence-3 topology: the
triangular bipyramid serialized under
`data/fixtures/candidates/closed_valence3_triangular_bipyramid`.

This is a proof/provider extension only. It does not broaden the Phase-4
production route, whose default provider request remains the exact canonical
tetrahedron. A production request for the bipyramid therefore continues to
reject before geometry, energy, or force mutation.

## Why this topology is next

The five-source triangular bipyramid is the smallest closed triangulated
sphere after the tetrahedron that contains Valence-3 vertices. Its topology is
independently identifiable:

| property | value |
| --- | ---: |
| vertices / edges / faces | `5 / 9 / 6` |
| Euler characteristic | `2` |
| vertex valences by stable ID | `3, 3, 4, 4, 4` |
| face triplets | six `3/4/4` faces |
| edge incidence | two oppositely oriented faces per edge |

It exercises a five-source row boundary and interaction between Valence-3 and
Valence-4 extraordinary vertices without introducing Valence 5, boundaries,
creases, ghosts, holes, or non-manifold structure. It is therefore a narrower
next step than the existing mixed `3/4/5` characterization fixture.

## Guarded provider contract

`OpenSubdivValence3RowProviderRequest` now contains an explicit topology
selector. Its default is `CanonicalTetrahedron`, preserving every existing
Phase-3 and Phase-4 call. Only proof code explicitly selects
`TriangularBipyramid344`.

The selected topology is validated before cache lookup. The bipyramid package
is fixed to:

```text
6 faces x 3 ordered samples x 7 derivative rows x 5 original sources
```

The same OpenSubdiv 3.7.0, Loop scheme, isolation level 5, Ptex identity,
constant-field invariants, and duplicated mixed-derivative rules apply. The
immutable cache is keyed by the explicit reviewed topology identity; the
tetrahedron and bipyramid cannot reuse one another's rows. Coordinates remain
excluded from both cache entries.

## Required proof boundary

The existing geometry/force harness now treats the bipyramid as provider-
applicable and requires:

- exact `3,3,4,4,4` valences and six `3/4/4` face triplets;
- provider rows equal to an independently constructed OpenSubdiv package;
- finite rows, row-sum invariants, Ptex identity, and isolation sensitivity;
- per-sample and stacked transpose identities;
- source-keyed scatter parity;
- finite nonzero bending, area, and volume forces;
- central finite-difference agreement for bending, area, and the selected
  full-divergence volume energy;
- zero net force and torque for the invariant internal energies; and
- rejection for missing opt-in, reversed winding, and an incorrect topology
  selector.

Passing this packet establishes mechanical feasibility only. Before any
production activation, the topology still needs a separate scientific
baseline decision, a separately serialized asymmetric-coordinate fixture,
quadrature convergence,
guarded transaction dry-run/postcondition evidence, output/checkpoint tests,
serial/OpenMP repeats, and an independently reviewed activation change.

## Initial measured proof

The first OpenSubdiv 3.7.0 run at isolation level 5 passed for both the
serialized coordinates and the fixed asymmetric perturbation already used by
the tetrahedron harness:

| observation | symmetric | asymmetric |
| --- | ---: | ---: |
| limit area | `1.0833627134931465` | `1.0961815450774315` |
| full-divergence volume | `0.10597381596532714` | `0.1075104362968244` |
| bending energy | `1337.553719758506` | `1345.9666747741842` |
| maximum bending finite-difference residual | `1.1369e-7` | `1.3195e-7` |
| maximum area finite-difference residual | `2.8866e-9` | `1.0098e-9` |
| maximum volume finite-difference residual | `2.2551e-10` | `1.4613e-10` |
| maximum net-force residual | `1.51e-16` | `2.41e-16` |
| maximum net-torque residual | `2.94e-13` | `7.34e-15` |

Both packages matched the independent OpenSubdiv row construction, and a
second provider call hit the correct topology-keyed cache. These values are
diagnostic observations, not an approved scientific baseline.
