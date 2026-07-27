# Valence-4 Production Geometry Staging

This review-gated lane adds the production C++ staging boundary needed before
the approved closed valence-4 octahedron can enter the real energy/force
caller. It remains default-off and does not publish geometry or enable a
route.

## Contract

`stage_guarded_valence4_face_geometry(...)` accepts caller-owned source-keyed
rows only after an explicit approval flag. Before returning output it
validates:

- the guarded canonical topology/source mapping;
- exact eight-face coverage and original source identities;
- exactly three samples per face;
- all seven derivative rows and finite coefficients;
- quadrature cardinality; and
- finite, nonnegative area plus finite legacy visible volume.

For every sample, the helper evaluates position, `d/dv`, and `d/dw` directly
from the canonicalized source-keyed rows. It then applies the current
production formulas:

```text
area += 0.5 * quadrature * norm(cross(dv, dw))
legacy volume += 0.16666666666 * quadrature
                 * position.x * cross(dv, dw).x
```

The result owns one `(face index, area, legacy volume)` record per face and
the corresponding global sums. It does not write `Face::elementArea`,
`Face::elementVolume`, `Param::area`, or `Param::vol`.

## Evidence

The focused C++ tests require default-off rejection, an independent
oriented-triangle oracle, exact global accumulation, malformed late-row
rejection, and complete mesh-state preservation. The OpenSubdiv-present
source-keyed adapter proof also sends fresh `8 x 3 x 7 x 6` rows through this
production helper and compares every face and both global totals with its
independent matrix-based geometry path within `1e-12`.

## Boundary

```text
production_geometry_staging: true
production_geometry_evaluated: true
geometry_publication_executed: false
not_production_routing: true
production_route_enabled: false
actual_production_force_path_executed: false
production_face_loop_executed: false
production_one_rings_populated: false
```

Default dependency behavior, formulas, source scatter, OpenMP scheduling and
reduction order, checkpoint/output, propagation, fixtures, boundary handling,
and broader-valence routing are unchanged.

The next separately reviewed step is to compose this staged geometry with the
existing staged scientific result so geometry-dependent force terms use the
same staged global area and volume before one atomic commit. Only after that
transaction and its serial/OpenMP parity gates pass should a real guarded
production caller be considered.
