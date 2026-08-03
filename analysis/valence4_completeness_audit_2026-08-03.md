# Valence 4 Completeness Audit - 2026-08-03

## Verdict

**EXTRA WORK TBD.**

The repository contains a real, guarded Valence-4 evaluator route for one exact
mesh: the six-vertex/eight-face canonical octahedron. Within that narrow direct
`Mesh::Compute_Energy_And_Force()` boundary, topology/source mapping,
OpenSubdiv row generation, geometry staging, membrane energy/force evaluation,
source-keyed OpenMP scatter, completion, and atomic rejection are substantially
implemented and well unit-tested.

It is not complete as an end-to-end SLIMED feature. The stock executable cannot
construct the approved octahedron, calls the legacy 11/12-control geometry path
before it reaches the guarded evaluator, and has no Valence-4-specific
checkpoint/output continuation test. The fixture contract also still explicitly
labels the octahedron candidate-only, scientifically unapproved, and unrouted,
which conflicts with the activated production route.

## Implemented and evidenced

| Area | Current state | Evidence |
| --- | --- | --- |
| Scope and topology | Exact canonical octahedron only: 6 vertices, 8 oriented faces, source IDs `0..5`, every vertex valence 4, closed physical faces, and empty production one-rings. Topology/order/identity drift rejects. | `src/mesh/Valence4_topology_source_mapping.cpp:13-131` |
| OpenSubdiv provider | Produces an owned `8 faces x 3 samples x 7 derivative rows x 6 sources` double-precision package. It validates Ptex identity, derivative presence, finite coefficients, partition/derivative sums, source coverage, and duplicated mixed rows. | `src/mesh/OpenSubdiv_valence4_row_provider.cpp:133-373`; `include/mesh/OpenSubdiv_valence4_row_provider.hpp` |
| Runtime routing | `Mesh::Compute_Energy_And_Force()` recognizes the exact-token runtime opt-in, rejects simultaneous Valence-4/5 route requests, invokes the guarded route, and returns after successful execution. Default behavior is unchanged when the gate is absent. | `src/energy_force/Compute_energy_and_force_on_mesh.cpp:589-642`; `src/energy_force/Valence4_face_loop_route_preflight.cpp:26-31,677-681,1856-1881` |
| Geometry | Source-keyed rows evaluate per-face limit area and the existing legacy visible-volume observable; global area/volume are staged and validated before publication. Exact `N=2` sample positions and three `1/3` weights are required for the provider-fed route. | `src/energy_force/Valence4_face_loop_route_preflight.cpp:192-259,343-415,551-594` |
| Energy and force | The route reuses `Mesh::element_energy_force_regular()` with explicit variable-cardinality shape rows. It computes bending energy, curvature, normals, bending force, area force, and volume force, then runs the existing completion phase for regularization, totals, constraints/scaffolding, and boundary handling. | `src/energy_force/Compute_energy_and_force_on_mesh.cpp:222-350,479-511,645+`; `docs/irregular_valence4_force_formula_proof.md` |
| Source mapping/scatter | Original source IDs are preserved independently of `Face::oneRingVertices`. Production uses per-thread `nVertices * 9` buffers and reduces in ascending thread/component order before publishing the three membrane-force families. | `src/energy_force/Compute_energy_and_force_on_mesh.cpp:175-350`; `src/energy_force/Source_keyed_kernel_call.cpp` |
| Atomicity | Topology, rows, geometry, source identities, finite coordinates, force destinations, face destinations, and quadrature are prevalidated. Dependency/topology/quadrature/destination failures are covered as no-mutation cases. | `src/energy_force/Valence4_face_loop_route_preflight.cpp`; `tests/test_valence4_face_loop_route_preflight.cpp` |
| Serial/default tests | A forced rebuild followed by the focused suite passed **55/55** default-build Valence-4 C++ tests. The fixture inventory also passed with 6/12/8 vertices/edges/faces and `{4: 6}` vertex valences. | Commands in "Verification performed" below |
| Dependency behavior | Default builds reject an explicit runtime request atomically when OpenSubdiv is absent. Ambient installation cannot activate routing. | `tests/test_valence4_face_loop_route_preflight.cpp:2817-2929,3221-3279`; `docs/irregular_valence4_opensubdiv_route_activation.md` |

## Concrete gaps

### P0 - End-to-end application entry is blocked

1. **The shipped executables never import the Valence-4 mesh.**
   `run_flat()` and the dynamics runner call `setup_flat()`
   (`src/Run_flat.cpp:85`, `src/Run_dynamics_flat.cpp:10`).
   `import_mesh_from_vertices_faces()` exists in `src/io/input.cpp:510`, but no
   production caller uses it. The canonical octahedron is constructed only by
   tests/experiments. Add a reviewed production mesh-input path (or a dedicated
   executable/input mode) and an end-to-end canonical fixture invocation.

2. **Startup geometry fails before the guarded evaluator can run.**
   `run_flat()` calls `mesh.calculate_element_area_volume()` at lines 111 and
   152, before `evaluate_energy_force()` at line 158. That geometry function
   calls `assert_supported_membrane_geometry_routing()`
   (`src/mesh/Mesh.cpp:52-79,337-339`), which rejects a closed physical face
   unless its production one-ring has 11 or 12 controls. The approved
   Valence-4 route deliberately requires empty one-rings. Route-aware geometry
   must be selected at initialization and all later standalone geometry
   refreshes, not only inside `Compute_Energy_And_Force()`.

Until both are fixed, the label "production route" is accurate only for a
direct library/API call to `Mesh::Compute_Energy_And_Force()`, not for a normal
SLIMED application run.

### P0 - Scientific/fixture authority contradicts activation

The exact fixture required by production still states:

- `status: candidate_only`;
- `scientifically_approved: false`;
- `not_production_routing: true`; and
- `production_route_enabled: false`.

These values are enforced by
`scripts/inventory_irregular_valence4_fixture_candidate.py:235-250` and
`tests/test_irregular_valence4_fixture_candidate_inventory.py:60-69`, while
`Mesh::Compute_Energy_And_Force()` contains an activated route for that fixture.
Resolve this explicitly: either obtain/record scientific approval and promote
the fixture contract, or revert/demote the route to proof-only status. Do not
leave production code and fixture authority disagreeing.

### P1 - Build/dependency naming and isolation are incomplete

Valence 4 has no `USE_OPENSUBDIV_VALENCE4` build option. Its provider is
compiled under `USE_OPENSUBDIV_REGULAR` (`src/mesh/OpenSubdiv_valence4_row_provider.cpp:16,51,133,141`), and the production harness also defines the regular macro. Valence 5 has a dedicated option in the Makefile. Add a dedicated
Valence-4 compile gate, or define and document a deliberate shared OpenSubdiv
backend option used uniformly by regular/3/4/5 routes. The current name couples
an extraordinary route to an unrelated regular-route feature switch and makes
dependency matrices ambiguous.

### P1 - Persistence and user-visible output need route-specific evidence

The route publishes the normal mesh/face/vertex fields, so generic CSV and V2
checkpoint code can serialize them. However, no Valence-4 test invokes
`write_model_restart_checkpoint()`, `load_model_restart_checkpoint()`, mesh CSV
output, or a resumed evaluation; searches of
`tests/test_valence4_face_loop_route_preflight.cpp` find none. The runtime route
choice is an environment variable and is not checkpointed.

Add an end-to-end test that:

1. evaluates the canonical route;
2. writes visible vertex/face/energy output and validates identity/cardinality;
3. writes and reloads a V2 checkpoint into the same canonical topology;
4. re-enables or explicitly restores the route policy; and
5. confirms resumed geometry, energy, and all force families against an
   uninterrupted run.

This will also establish whether the production input-mode work above rebuilds
the empty-one-ring topology correctly on restart.

### P1 - OpenSubdiv-present serial/OpenMP release gate was not reproducible here

The repository contains wrappers and documentation for provider-fed serial vs
OpenMP parity at `1e-12`, plus OpenSubdiv-enabled C++ tests. This workstation
has no `OPENSUBDIV_ROOT`, so the real provider, default evaluator activation,
and actual OpenMP route were not executed during this audit. Treat a fresh
OpenSubdiv-present serial/OpenMP run against the intended supported version as
a release requirement, not as currently revalidated evidence.

### P2 - Scope is one serialized topology, not general Valence 4

The implementation hard-codes counts, source IDs, face order/orientation, and
empty one-rings for one octahedron. It does not support reordered equivalent
octahedra, arbitrary all-Valence-4 closed meshes, mixed-valence patches,
boundaries, ghosts, periodic meshes, or changing topology. This is acceptable
only if the feature is named and documented as the **canonical-octahedron
Valence-4 route**. General Valence-4 support remains substantial future work.

### P2 - Historical inventory tests are not maintainable at current `main`

The focused Python inventory discovery ran 85 tests and reported 33 failures
and 20 skips. The failures were predominantly frozen PR-scope checks comparing
the current repository to old base commits and asserting superseded states such
as "not called by production." They do not diagnose the current route and
cannot serve as a head-of-tree regression suite. Replace or supplement them
with state-based current-contract tests; retain historical inventories only as
archival evidence.

The Makefile also does not emit header dependency files. A first focused C++
run linked stale test objects after a header-layout change and produced two
false failures; a forced rebuild passed 55/55. Header dependency tracking would
remove this source of misleading validation.

## Verification performed

From WSL at repository head/worktree state on 2026-08-03:

```text
make -B test -j2                         timed out while compiling
make test -j4                            PASS (completed the forced rebuild)
./bin/test_main \
  --gtest_filter=ValenceFourFaceLoopRoutePreflight.*
                                            PASS: 55/55
python3 scripts/inventory_irregular_valence4_fixture_candidate.py --check
                                            PASS: 6 vertices, 12 edges,
                                            8 faces, all valence 4
python3 scripts/run_irregular_valence4_opensubdiv_row_provider.py --json
                                            SKIP: OPENSUBDIV_ROOT unset
python3 -m unittest discover -s tests \
  -p 'test_irregular_valence4_*inventory.py'
                                            FAIL: 33, SKIP: 20 of 85;
                                            mostly frozen changed-path/base
                                            assertions, as described above
```

No production or CUDA source was changed by this audit.
