# Valence-4 Production-Call Shadow Parity

This review-gated proof invokes the merged atomic valence-4 publication
transaction from a production-shaped shadow and compares its complete output
between serial and OpenMP builds. It does not install or execute a production
route.

## Compared output

Both builds consume the same fresh OpenSubdiv `8 x 3 x 7 x 6` row package and
the approved closed valence-4 octahedron. The machine-readable comparison
binds:

- all six vertices' `fBend`, `fArea`, and `fVolume` components;
- all eight faces' mean curvature, bending energy, and normal;
- area computed from each binary's evaluated limit-surface rows; and
- legacy visible volume computed from the same evaluated position and
  oriented-area rows.

The comparison requires every output to be finite, the membrane-force output
to be nonzero, exact source and face identity, and a maximum absolute delta no
greater than `1e-12`.

Area and legacy volume are not copied from the shared force-proof package.
Each binary evaluates the source-keyed rows against its control-point matrix,
then uses the production quadrature weights and the current legacy
`position.x * cross(dv, dw).x` accumulation. Both outputs must also agree with
the independent Python geometry oracle within `1e-12`. The oracle explicitly
uses the current production legacy-volume factor `0.16666666666`, rather than
silently substituting exact `1/6`.

The OpenMP build runs with `OMP_DYNAMIC=FALSE` and four requested threads.
Because the atomic publication helper itself is a transaction rather than a
parallel reduction, this lane also requires the independent production-shaped
OpenMP proof. That predecessor exercises actual OpenMP teams `1`, `2`, `3`,
`4`, and `8`, five repeats each, the `6 x 9` thread buffers, ascending-thread
reduction, exact collision coverage, and an independent long-double oracle.

## Boundary

```text
proof_only: true
production_call_shadow: true
not_production_routing: true
production_route_enabled: false
actual_production_force_path_executed: false
production_face_loop_executed: false
atomic_face_loop_publication_executed: true
production_shaped_geometry_evaluated: true
serial_openmp_output_parity_passed: true
actual_openmp_runtime_parity_passed: true
```

No production face-loop caller is added. Default dependency behavior,
`Face::oneRingVertices`, formulas, source scatter, OpenMP scheduling and
reduction order, checkpoint/output, propagation, fixtures, optimizer
behavior, boundary handling, and broader-valence routing are unchanged.

After this proof, guarded route activation remains a separate production C++
change requiring explicit reviewer and user approval.
