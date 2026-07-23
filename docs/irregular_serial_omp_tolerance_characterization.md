# Irregular Serial/OpenMP Tolerance Characterization

This is a tests/docs/scripts/experiments-only characterization lane. It records
serial/OpenMP behavior for the supported positive-depth 11-control `4+3+4`
route without expanding the scientific or production contract.

No production C++ behavior, build policy, dependencies, OpenSubdiv integration,
routing formula, scatter order, OpenMP scheduling, reduction behavior, output
format, checkpoint format, or propagation behavior changes.

## Current Fixture Boundary

The repository now contains the explicitly approved narrow scientific
stand-in under `data/fixtures/closed_valence5`. The fixture decision is:

- checked-in `data/example` topology has regular 12-control faces and mixed
  valence discovery leads, but no physical all-valence-5 11-control candidate;
- coordinate-only Gag and shape CSV files do not include face connectivity;
- the generated closed icosahedron coordinates/connectivity are serialized as
  a fixed-boundary fixture with 20 physical 11-control faces;
- the waiver is limited to the existing positive-depth 11-control route and
  does not approve broader valences or OpenSubdiv irregular routing.

Production setup gives every face an ordered 11-slot one-ring with nine unique
source IDs. The two duplicate local source slots are preserved and aggregated
through `Face::oneRingVertices`.

## Characterized Outputs

The original focused test
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

The approved fixture now adds an actual executable comparison through
`scripts/run_irregular_valence5_fixture_parity.sh`. It compiles the real
production evaluator in serial and OpenMP modes and compares global/face
energy, all vertex force components, normals, area, legacy volume, and mean
curvature. The maximum observed absolute delta was
`1.4210854715202004e-14`, below the retained `1.0e-10` policy.

## What This Does Not Claim

This characterization does not make scheduler assignment portable. OpenMP may
assign faces to different threads, and any face sharing can change
floating-point addition order. The current production contract remains the
thread-local buffer shape and ascending thread-buffer reduction order described
in `docs/force_formula_scatter_equivalence.md`.

This characterization validates the existing route only against the approved
closed valence-5 stand-in. It does not establish broader-valence physics or an
OpenSubdiv irregular routing contract.

## Companion Check

Regenerate the inventory with:

```console
python3 scripts/inventory_irregular_serial_omp_tolerance.py
```

Use the check mode during validation:

```console
python3 scripts/inventory_irregular_serial_omp_tolerance.py --check
```
