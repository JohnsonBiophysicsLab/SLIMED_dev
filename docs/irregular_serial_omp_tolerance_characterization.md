# Irregular Serial/OpenMP Tolerance Characterization

This is a tests/docs/scripts-only characterization lane. It records what can
be checked today for the supported positive-depth 11-control `4+3+4` route
without expanding the scientific or production contract.

No production C++ behavior, build policy, dependencies, OpenSubdiv integration,
routing formula, scatter order, OpenMP scheduling, reduction behavior, output
format, checkpoint format, or propagation behavior changes.

## Current Fixture Boundary

The current repository still has no checked-in physical 11-control fixture
with explicit non-ghost status and reviewed scientific expectations. The
fixture discovery lane found:

- checked-in `data/example` topology has regular 12-control faces and mixed
  valence discovery leads, but no physical all-valence-5 11-control candidate;
- coordinate-only Gag and shape CSV files do not include face connectivity;
- the generated closed icosahedron topology maps all faces to 11-control, but
  it is topology-only evidence, not a production scientific fixture.

Because of that, this lane does not compare serial and OpenMP executables on a
representative production irregular mesh. Doing so would require either a
reviewed fixture or production hooks/fixture decisions outside the approved
low-risk scope.

## Characterized Outputs

The focused test
`SurfaceSubdivisionCharacterization.SyntheticIrregularPatchSerialOpenMpReductionToleranceEnvelope`
uses the existing synthetic positive-depth 11-control route to produce
deterministic area, volume, curvature-energy, and force-row outputs for
several perturbed irregular patches. It then replays only the documented
production accumulation shape in test code:

- serial-like accumulation: all irregular force rows scatter into one
  vertex-major buffer in face order;
- OpenMP-compatible accumulation: face rows scatter into per-thread
  vertex-major buffers, then reduce buffers in ascending thread-index order;
- compared quantities: total area, total volume, face curvature-energy sum,
  and all per-vertex curvature, area, and volume force components.

The tolerance envelope is `1.0e-10` absolute for force components and the
aggregated scalar quantities in this synthetic split-reduction comparison.
Existing route tests still use tighter local tolerances where they compare a
single production face directly to independent test-side subdivision and
transpose math.

## What This Does Not Claim

This characterization does not make scheduler assignment portable. OpenMP may
assign faces to different threads, and any face sharing can change
floating-point addition order. The current production contract remains the
thread-local buffer shape and ascending thread-buffer reduction order described
in `docs/force_formula_scatter_equivalence.md`.

This characterization also does not validate scientific correctness for a real
irregular membrane fixture. It is mechanical evidence that the current
supported 11-control route outputs remain stable under the documented
serial-like and OpenMP-compatible reduction shapes within the stated synthetic
tolerance.

## Companion Check

Regenerate the inventory with:

```console
python3 scripts/inventory_irregular_serial_omp_tolerance.py
```

Use the check mode during validation:

```console
python3 scripts/inventory_irregular_serial_omp_tolerance.py --check
```
