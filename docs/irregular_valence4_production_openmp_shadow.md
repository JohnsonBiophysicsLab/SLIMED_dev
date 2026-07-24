# Valence-4 Production-Topology and OpenMP Shadow

This lane follows the proof-only valence-4 scatter-shape evidence from PR
#118. It closes two evidence gaps without enabling a production route:

- the approved octahedron is loaded through production `Mesh` topology setup;
- the eight OpenSubdiv-derived face-force contributions are accumulated by a
  real OpenMP runtime using the production `6 * 9` buffer and reduction shape.

The report remains:

- `proof_only: true`
- `production_call_shadow: true`
- `not_production_routing: true`
- `production_route_enabled: false`
- `actual_production_force_path_executed: false`

Run it explicitly with:

```bash
OPENSUBDIV_ROOT=/tmp/slimed-opensubdiv-install \
OPENSUBDIV_CXXFLAGS='-arch arm64' \
scripts/run_irregular_valence4_production_openmp_shadow.sh \
  --json --require-opensubdiv
```

Without `OPENSUBDIV_ROOT`, the wrapper returns a clean `status: skipped`.
The default build, test, dependency, and runtime policies are unchanged.

## Production topology identity

The standalone experiment reads the approved
`data/fixtures/candidates/closed_valence4_octahedron` CSVs and calls
production `Mesh::setup_from_vertices_faces`. It independently checks:

- six coordinates match the serialized fixture;
- eight oriented face rows match the serialized connectivity;
- every source vertex has valence four;
- all eight faces are physical, non-boundary faces.

This check also records the current unsupported-route boundary:
`Face::oneRingVertices` is empty for every face. The proposed per-face source
mapping is therefore explicitly proof-local original fixture source IDs
`0..5`; it is not represented as a populated production one-ring.

## OpenMP runtime evidence

The existing force proof now emits its eight face-local `fBend`, `fArea`, and
`fVolume` rows. The runner serializes those rows into a temporary,
machine-readable input for the standalone experiment.

Before flattening, an independent accumulator sums in `long double` by source
ID, force kind, and axis. A separate exact-index sentinel oracle checks all 54
destinations in the reviewed layout:

```text
source_id * 9 + force_kind * 3 + axis
```

The actual OpenMP loop uses static face scheduling and one 54-component buffer
per thread. Reduction proceeds by source, force kind, axis, then ascending
thread index. `OMP_DYNAMIC=FALSE` is set both in the wrapper environment and
through the OpenMP runtime.

Requested thread counts `1`, `2`, `3`, `4`, and `8` each run five times.
Every run must obtain the requested team size, remain finite, reproduce its
first result, and agree with the long-double oracle under an absolute `1e-12`
tolerance.

Observed maximum oracle deltas were:

| Threads | Maximum absolute delta |
| ---: | ---: |
| 1 | `0` |
| 2 | `3.552713678800501e-15` |
| 3 | `2.1316282072803006e-14` |
| 4 | `7.105427357601002e-15` |
| 8 | `0` |

All five repeats were identical for every requested thread count. All eight
faces contributed finite, nonzero rows. Every one of the 54 destination
components received contributions from all eight faces, so there were no
uncovered or single-contribution component slots.

## Boundary

This evidence does not call the production valence-4 force path because that
path does not exist. In particular, it does not:

- populate production `Face::oneRingVertices`;
- install an OpenSubdiv route;
- change formulas, scatter code, OpenMP scheduling, or reductions;
- change default build/dependency behavior;
- change checkpoint, output, propagation, or fixture files.

The remaining work is a separately reviewed topology-adapter design for
valence-4 source mappings. Only after that mapping is represented in a guarded
production-call path can real production serial/OpenMP parity and route
readiness be evaluated.
