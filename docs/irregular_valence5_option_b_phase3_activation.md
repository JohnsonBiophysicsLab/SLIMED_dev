# Option B Phase 3 guarded production activation

## Activated boundary

This change implements the separately approved Phase 3 boundary for the
accepted closed, positive-depth valence-5 topology. An OpenSubdiv-enabled
binary routes `Mesh::Compute_Energy_And_Force()` through the reviewed Phase 2
transaction only when:

```text
SLIMED_USE_OPENSUBDIV_VALENCE5=1
```

The production gate is distinct from the Phase 2 proof-only gate. When the
production gate is absent, the evaluator executes the unchanged dependency-free
`11 = 4 + 3 + 4` subdivision-matrix fallback. Unsetting
`SLIMED_USE_OPENSUBDIV_VALENCE5` is therefore the complete rollback; it needs
no rebuild, checkpoint conversion, or mesh-state migration.

Default builds remain OpenSubdiv-free. If the production gate is requested in
a dependency-disabled build, the stock provider rejects and the default
evaluator throws before the first mesh write. Unsupported topology, identity,
quadrature, source mapping, or destination state is rejected through the same
atomic preflight. Simultaneously requesting the valence-4 and valence-5
extraordinary routes is also rejected before mutation.

## Compatibility boundary

The activated route preserves the reviewed Option B semantics and source-keyed
scatter from Phases 1 and 2. It does not clear, reorder, populate, or consume
the existing 11-control production one-rings. Regular and valence-4 routing,
unsupported irregular topology behavior, ten-channel CSV schemas, and V1/V2
checkpoint formats remain unchanged.

The Phase 3 harness calls the public default evaluator and compares it with the
reviewed direct transaction under the fixed `1e-10` production tolerance. It
also verifies the dependency-present and dependency-absent modes, gate-absent
rollback, conflicting-route rejection, fixed scientific expectations,
serial/OpenMP behavior, exact repeatability, output writers, and checkpoint
round trips.

The reviewed WSL/OpenSubdiv 3.7.0 activation run passed with:

- default-versus-direct routed observables and forces within `1e-10`;
- fixed global and per-face energy expectation differences of `0.0`;
- accepted geometry maximum difference `2.0762915764471757e-7` under `3e-7`;
- serial/OpenMP membrane-force maximum difference
  `4.085620730620576e-14`;
- serial/OpenMP energy/geometry maximum difference
  `6.175615574477433e-16`;
- exact repeatability and exact output/checkpoint round trips;
- dependency-free and enabled-build fallback difference `0.0` when the gate
  is absent.

The independent long-double oracle and precision-specific scientific
rebaseline remain binding through the merged Phase 2 proof. Activation does
not claim stock/current parity and does not widen any tolerance.

## Reproduce in WSL/Linux

Dependency-free rollback and atomic-rejection contract:

```bash
scripts/run_irregular_valence5_option_b_phase3_activation.sh --check --json
```

Full activation suite:

```bash
OPENSUBDIV_ROOT=/opt/opensubdiv-3.7.0 \
  scripts/run_irregular_valence5_option_b_phase3_activation.sh \
  --check --json --require-opensubdiv
```
