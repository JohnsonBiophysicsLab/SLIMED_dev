# Guarded OpenSubdiv Valence-4 Route Activation

This lane connects the reviewed valence-4 OpenSubdiv production transaction to
`Mesh::Compute_Energy_And_Force()` for one approved topology: the canonical
closed valence-4 octahedron.

## Two Explicit Gates

The route is available only when both conditions are true:

1. the binary is built with
   `USE_OPENSUBDIV_REGULAR=1 OPENSUBDIV_ROOT=/path/to/opensubdiv`; and
2. the process sets `SLIMED_USE_OPENSUBDIV_VALENCE4=1`.

The runtime gate is false when unset or set to `0`, `false`, or `off`, using
either lowercase or uppercase spellings. Ambient OpenSubdiv installation
never selects the route.
The default dependency-free build remains OpenSubdiv-free.

## Atomic Canonical Route

When requested, `Mesh::Compute_Energy_And_Force()` calls
`evaluate_guarded_valence4_opensubdiv_production_route(...)` before the
ordinary evaluator mutates geometry or force state. The route delegates to the
reviewed complete transaction:

- exact canonical topology, orientation, source coverage, and empty production
  one-rings;
- exact ordered `N=2` quadrature samples and three `1/3` weights;
- OpenSubdiv-generated `8 x 3 x 7 x 6` source-keyed rows;
- geometry/scientific staging and complete destination validation;
- current force formulas, production-shaped source scatter, existing OpenMP
  reduction, and shared completion; and
- atomic publication only after every precondition succeeds.

Successful execution marks `productionRouteEnabled` and
`defaultEvaluatorCaller` only after the reviewed transaction succeeds.
Dependency absence or topology, orientation, quadrature, row, or destination
drift throws before mutation.

## Evidence Boundary

Default-build tests prove an explicit runtime request rejects atomically when
the dependency is unavailable and that the unset runtime gate is inert.
OpenSubdiv-enabled tests prove the real evaluator entry matches the reviewed
explicit transaction for area, legacy visible volume, energy, normals, and all
eight force families, and that orientation drift rejects atomically.

This activation does not populate `Face::oneRingVertices`, change formulas or
scatter semantics, alter OpenMP reductions, change default dependency policy,
or touch checkpoint/output/propagation behavior. It does not authorize any
other valence or topology.
