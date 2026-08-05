# Valence-3 Phase-5 Triangular-Bipyramid Quadrature Study

This packet continues Phase 5 with two changes:

1. the asymmetric triangular-bipyramid coordinates are now independently
   serialized under
   `data/fixtures/candidates/asymmetric_valence3_triangular_bipyramid`; and
2. both symmetric and asymmetric fixtures are evaluated with a fixed nested
   affine-subtriangle quadrature study.

The packet is proof-only. It does not select a new integration plan, change
the immutable production row packages, or broaden the exact-tetrahedron
production route.

## Nested rule

Each Ptex parameter triangle starts at depth 0. A refinement step connects
the three edge midpoints and replaces every triangle by four consistently
oriented subtriangles. The existing three interior barycentric samples are
affinely mapped into every subtriangle. The subtriangle area factor is folded
into the quadrature weight, so weights remain positive and sum to one per
coarse face.

| depth | subtriangles | samples per coarse face |
| ---: | ---: | ---: |
| 0 | 1 | 3 |
| 1 | 4 | 12 |
| 2 | 16 | 48 |
| 3 | 64 | 192 |
| 4 | 256 | 768 |

Every sample remains strictly inside the Ptex triangle. OpenSubdiv 3.7.0
generates value, first-derivative, and second-derivative rows at isolation
level 5. The existing `Mesh::element_energy_force_regular()` algebra consumes
those rows with fixed material parameters and fixed area/volume reference
targets across all depths.

The study targets from the Valence-3 implementation plan remain unchanged:

- global area, full-divergence volume, and total-energy change at most `1e-6`;
- source force-component scale change at most `1e-5`; and
- both limits must hold over the last two successive depth transitions.

The ordinary row-invariant target also remains `1e-12`. The study records
structural row finiteness separately so an invariant miss can be reported
without widening the production/provider tolerance.

## Measured result

The study completed, but neither fixture met the activation targets:

| fixture | depth 3→4 global change | depth 3→4 force change | depth-4 maximum row-sum residual |
| --- | ---: | ---: | ---: |
| symmetric `3/4/4` bipyramid | `2.3286725851e-4` | `1.2813709798e-3` | `1.0516032489e-12` |
| asymmetric `3/4/4` bipyramid | `2.3772548947e-4` | `1.5142500944e-2` | `1.0516032489e-12` |

The preceding depth 2→3 changes were also above target. Depth-4 rows remained
finite and structurally complete, but their maximum constant-field residual
was slightly above the fixed `1e-12` target. No tolerance was widened.

The evidence runner therefore reports:

```text
study_completed: true
scientific_targets_met: false
activation_blocked: true
production_route_enabled: false
```

This is a successful evidence packet and a failed scientific activation gate.
The current three-sample plan must not be described as converged for the
triangular bipyramid. Future work must decide whether to investigate a
different integration strategy, extend a bounded convergence study with an
independent oracle, or keep this topology unsupported.
