# Adaptive edge-flipping feasibility and implementation gate

Date: 2026-08-03

## Conclusion

Adaptive edge flipping is **algorithmically feasible but not production-ready
in the current mesh architecture**. A local geometric proof gate can be
implemented safely; a topology mutation cannot yet be made safe without first
adding topology ownership, a general rebuild transaction, evaluator coverage,
cache invalidation, material-label policy, optimizer reset semantics, and a
topology-aware checkpoint format.

This work therefore starts only the proof layer:

- `include/mesh/Adaptive_edge_flip_quality.hpp` provides a header-only,
  coordinate-only evaluator for one oriented two-triangle hinge;
- `tests/test_adaptive_edge_flip_quality.cpp` covers acceptance, Delaunay
  neutrality, hysteresis, degeneracy, nonfinite input, and invalid options;
- no `Mesh`, face, vertex, cache, optimizer, dynamics, checkpoint, production
  route, or CUDA state is mutated.

The production feasibility gate does **not** pass yet. Candidate selection and
mesh mutation remain explicitly out of scope.

## Research basis and metric choice

Fisher, Springborn, Schröder, and Bobenko define the local intrinsic Delaunay
condition for an interior edge by the sum of the two opposite angles: the edge
is locally Delaunay when that sum is at most pi. They also show an edge-flip
algorithm on piecewise-flat surfaces and emphasize that a proper intrinsic
implementation needs an edge-based representation; triangle-vertex incidence
alone is not suitable for the non-regular cases the algorithm may produce:

- [An Algorithm for the Construction of Intrinsic Delaunay Triangulations with
  Applications to Digital Geometry Processing](https://page.math.tu-berlin.de/~bobenko/papers/InDel.pdf)

That paper's intrinsic operation preserves the piecewise-flat carrier by
representing the new edge as a geodesic in the old surface. A SLIMED
connectivity flip that simply replaces diagonal `(a,b)` by the straight 3D
chord `(c,d)` is an **extrinsic retriangulation**. On a non-coplanar hinge it
changes the piecewise-flat carrier, and even on a planar hinge it changes the
Loop subdivision limit surface. The Delaunay test is therefore a candidate
quality predicate, not a proof of physical-energy continuity.

OpenSubdiv likewise treats topology as construction-time input to a
`Far::TopologyRefiner`; its stencil-table performance model assumes topology
can be amortized when it does not change. A flip consequently requires new
topology/refiner/stencil state, not just new vertex positions:

- [OpenSubdiv API overview](https://opensubdiv.org/docs/api_overview.html)

### Proof metric

For consistently oriented old faces `(a,b,c)` and `(b,a,d)`, the proof helper
evaluates proposed faces `(c,d,b)` and `(d,c,a)`. It accepts only when all of
the following hold:

1. options and all four coordinates are finite;
2. both old and proposed triangles pass a scale-independent degeneracy test,
   `|cross(e1,e2)| / max_edge_squared > tolerance`;
3. the old edge violates intrinsic Delaunay by a strict hysteresis,
   `angle_c + angle_d > pi + epsilon_angle`;
4. the minimum of all six triangle angles increases by more than
   `epsilon_min_angle`;
5. the worse mean-ratio quality of the two triangles does not regress (or
   improves by a configured amount), using
   `q = 4 sqrt(3) area / sum(edge_length_squared)`;
6. both proposed oriented normals have sufficient positive alignment with the
   sum of the old oriented normals.

Defaults are intentionally strict comparisons with small hysteresis:

| Option | Default |
|---|---:|
| Delaunay angle hysteresis | `1e-6` radians |
| minimum-angle improvement | `1e-6` radians |
| mean-ratio improvement | `0` (non-regression) |
| relative degeneracy tolerance | `1e-12` |
| minimum orientation cosine | `0` (valid range `[0,1)`) |

These are proof defaults, not calibrated production constants. Production
values must be nondimensionalized and characterized across mesh resolution,
curvature, and numerical precision.

## Current topology ownership

### Canonical connectivity is face-only

The active topology is implicit in `Mesh::faces[*].adjacentVertices` plus
derived lists on faces and vertices. `Mesh.hpp` contains commented-out
`Edge`/`Halfedge` vectors. `src/mesh/HalfedgeMesh.cpp` is also entirely
commented out, and its sketch refers to a non-current `face.vertices` member.
There is no active owner for a unique undirected edge, its two incident faces,
or its two oriented halfedges.

This makes even candidate enumeration nontrivial. A production implementation
must first build an edge-incidence index keyed by ordered vertex pair
`(min(u,v), max(u,v))` and reject:

- an edge with other than exactly two incident physical faces;
- repeated vertices in either triangle;
- a proposed `(c,d)` edge that already exists elsewhere;
- inconsistent orientation of the shared edge;
- duplicate or non-manifold proposed faces.

An active halfedge representation is preferable if flips will be frequent.
A validated edge-incidence table rebuilt transactionally from faces is an
acceptable first stage if flips remain infrequent.

### Existing rebuild routines are not a general topology transaction

`Mesh::setup_flat()` calls:

1. `set_adjacent_faces_of_vertices_sorted()`;
2. `set_adjacent_vertices_of_vertices_sorted()`;
3. `set_adjacent_faces_of_faces()`;
4. `sort_vertices_on_faces()`;
5. `determine_ghost_vertices_faces()`;
6. `set_one_ring_vertices_sorted()`.

Those functions cannot simply be replayed after a flip:

- the sorting half of `set_adjacent_faces_of_vertices_sorted()` derives order
  from rectangular `nFaceX/nFaceY` index formulas, not connectivity;
- `setup_from_vertices_faces()` does not call
  `set_adjacent_faces_of_faces()` or `sort_vertices_on_faces()` and still calls
  the grid-specific vertex-face sorter;
- `faces_share_edge()` uses `std::set_intersection` directly on oriented face
  vertex vectors, although that algorithm requires sorted ranges;
- `set_adjacent_faces_of_faces()` considers a face to share an edge with
  itself, preallocates exactly three entries, and is therefore not a safe
  general manifold adjacency builder;
- `sort_vertices_on_faces()` assumes three valid adjacent-face entries and can
  loop until every face is reached from face zero;
- `set_one_ring_vertices_sorted()` recognizes only its current 12-control
  regular case and narrow 11-control irregular case.

Before mutation, add one topology-independent rebuild function that derives
all adjacency and orientation from the face index list, validates a connected
orientable two-manifold (or explicitly supported boundary components), and
commits only after the entire rebuilt state is valid.

## Subdivision and energy implications

An edge flip changes the valences of all four hinge vertices:

- old-edge endpoints `a` and `b`: valence minus one;
- opposite vertices `c` and `d`: valence plus one.

It also changes the two-ring control neighborhoods for more than the two
edited faces. Today the legacy face loop expects 12-control regular patches or
the narrow 11-control irregular convention. The guarded Valence 3, 4, and 5
OpenSubdiv providers recognize exact canonical fixtures/topologies, not an
arbitrary local mixture created inside a large mesh. A single flip can produce
unsupported 3/4/5/6/7 combinations even if both old triangles were regular.

Therefore, the production route must reject a candidate unless **every face in
the affected two-ring has a validated evaluator and source-keyed force scatter
after the proposed valence changes**. Exact tetrahedron/octahedron/closed
Valence-5 fixture support is not sufficient for this gate.

The physical energy is not continuous across connectivity. Loop basis
functions, limit positions, derivatives, quadrature geometry, curvature,
forces, and per-face observables depend on topology. Keeping coordinates fixed
does not keep the represented limit surface fixed. A quality-improving flip can
therefore cause a finite jump in bending, area, volume, regularization, tilt,
and insertion-related energies.

A later topology transaction must:

1. evaluate and store the complete pre-flip accepted state;
2. stage the connectivity edit and rebuild every affected derived object;
3. recompute complete energy, geometry, and force through the same production
   evaluator used after acceptance;
4. require finite results and an explicitly reviewed energy-jump policy;
5. atomically commit or restore topology, derived state, energy, force, face
   observables, caches, and optimizer state.

Energy non-increase is not automatically the right policy: connectivity is a
discretization choice, not a physical degree of freedom. Initial scientific
approval should instead bound relative changes against mesh-refinement and
no-flip reference studies. If flips are modeled as thermal Monte Carlo moves,
proposal symmetry/detailed balance and RNG/checkpoint state need a separate
design.

## Cache and OpenSubdiv invalidation

`RegularLimitSurfaceRowCache` is invalidated by `setup_flat()` and
`setup_from_vertices_faces()`. It also fingerprints face topology, so a later
read may detect a changed mesh. That is not enough for a safe mutation
contract:

- mutation must be serialized against concurrent cache readers;
- the cache must be explicitly invalidated before readers resume;
- all OpenSubdiv topology refiners, patch/stencil tables, source mappings, and
  any cached source-keyed rows must be rebuilt for the new topology;
- face-index-to-row identity must be revalidated;
- a monotonically increasing `topologyGeneration` should key all derived
  topology state.

The cache is currently a private `Mesh` member with no public topology-change
transaction. Add invalidation inside that transaction rather than exposing a
general caller-controlled cache reset.

## Boundary, ghost, periodic, and insertion policy

### Boundary and ghost regions

Ghost and boundary flags are assigned from rectangular grid index bands.
They are not inferred from general topology. First production scope should
reject any edge when either incident face or any hinge vertex is ghost,
boundary, fixed-boundary, periodic, periodic-reflective, or has a reflective
counterpart. It should also reject candidates whose affected two-ring touches
those states.

### Periodicity

Periodic behavior duplicates and synchronizes coordinate bands by fixed index
arithmetic. Flipping only one image of a periodic edge would make periodic
copies topologically inconsistent. Periodic support requires identification of
topological equivalence classes and an atomic, orientation-correct flip of all
images. Until that exists, periodic meshes fail the feasibility gate.

### Insertion and spatial/material labels

Insertion membership and spontaneous curvature are face-owned and face-index
driven. Reusing the same two face indices after a flip silently moves the
physical support of those labels. Scaffolding code also writes spontaneous
curvature through vertex-adjacent face lists.

Initial scope must reject a hinge when the two faces differ in
`isInsertionPatch`, `spontCurvature`, layer, ghost, or boundary classification,
and should reject any insertion face entirely until a reviewed material-field
transfer rule exists. A production transaction must rebuild scaffold-adjacent
face effects after connectivity changes.

## Optimizer and dynamics timing

### Minimization

Do not flip inside `linear_search_for_stepsize_to_minimize_energy()`. That loop
assumes a fixed objective and restores only coordinates on rejected trials. A
connectivity change would invalidate the Wolfe derivative, `forcePrev`, NCG
direction, per-face `energyPrev`, and coordinate-only rollback.

The earliest plausible timing is a dedicated remeshing phase after a coordinate
step has been accepted and fully evaluated, but before the next line search.
After any committed flip:

- recompute complete energy and force;
- copy the refreshed state into the previous-state snapshots consistently;
- reset NCG to steepest descent and clear line-search history;
- update reference coordinates only under an explicit regularization policy;
- record the topology event before output/checkpoint.

Thermal trials currently restore coordinates only. Adaptive flipping must stay
disabled during such trials until rollback includes connectivity and derived
state.

### Dynamics

`DynamicMesh::setup_flat()` builds `mesh2surface` and its inverse
`surface2mesh` once from vertex adjacency. Both become stale after a flip.
The current builder also hard-codes regular valence-six weights. Dynamics must
remain out of scope until these operators can be rebuilt for arbitrary valence,
validated for invertibility/conditioning, and swapped atomically with topology.

## Output and restart compatibility

Restart V2 writes vertex coordinates/forces and face geometry/energy, but it
does not write `Face::adjacentVertices` or any topology event. It only validates
vertex and face counts on load. A run containing flips would restart from the
input mesh's original connectivity while loading observables computed on a
different connectivity.

Production activation therefore requires a new checkpoint version containing:

- oriented face connectivity and a topology hash/generation;
- face-owned material/insertion/layer classifications needed to reconstruct
  the accepted state;
- deterministic flip-policy/version metadata if replay is supported;
- current optimizer reset state after the last topology transaction.

V1/V2 remain valid for static-topology runs. A new loader must install and
validate checkpoint topology before loading face observables, then rebuild all
adjacency, one-rings, evaluator rows, and caches. Output also needs either
connectivity snapshots at each topology change or an ordered flip-event log;
the initial `face.csv` alone is insufficient.

## Concrete production feasibility gate

All gates are mandatory and ordered.

### Gate A — pure metric proof (implemented)

- deterministic, side-effect-free single-hinge evaluator;
- Delaunay/min-angle/mean-ratio hysteresis;
- finite, degeneracy, and orientation checks;
- scale, rigid-transform, and label-order characterization.

Status: **started and focused tests pass**. Scale/rigid-transform property tests
are still recommended before treating constants as calibrated.

### Gate B — topology transaction

- unique edge-incidence ownership;
- general adjacency/orientation rebuild independent of grid indices;
- manifold, duplicate-edge, duplicate-face, Euler characteristic, connected
  component, and boundary-loop invariants;
- atomic stage/validate/commit/rollback;
- deterministic non-conflicting candidate ordering.

Status: **blocked by current topology architecture**.

### Gate C — evaluator coverage

- every affected two-ring route supported after valence changes;
- source-keyed energy/force and finite-difference proof for mixed valence;
- explicit invalidation/rebuild of Loop/OpenSubdiv rows, topology refiners,
  stencil tables, and regular cache;
- serial/OpenMP parity and race-free topology-generation handling.

Status: **blocked; exact closed Valence 3/4/5 routes do not provide general
mixed-patch coverage**.

### Gate D — scientific continuity

- pre/post area, volume, curvature energy, total energy, and force comparison
  over flat, curved, irregular, and refined fixtures;
- mesh-refinement convergence showing remeshing error decreases;
- reviewed energy-jump and normal/dihedral thresholds;
- no force/energy publication before the complete transaction validates.

Status: **not performed**.

### Gate E — lifecycle compatibility

- accepted-step timing and NCG reset proof;
- thermal rollback policy;
- insertion/scaffold/material transfer policy;
- boundary, ghost, and periodic rejection or paired-flip implementation;
- topology-aware checkpoint/restart and output reconstruction;
- dynamics operator rebuild, if dynamics is later included.

Status: **not implemented**.

### Gate F — guarded activation

- runtime opt-in, default-off and fail-loud behavior;
- deterministic candidate-independent-set construction;
- cooldown/topology-generation hysteresis to prevent flip-flop as coordinates
  move;
- production benchmarks and long-run topology/energy invariants;
- rollback by disabling the route.

Status: **not authorized**.

## Proposed deterministic candidate algorithm

Once Gates B–E exist:

1. Build the unique undirected edge table from an immutable accepted topology
   snapshot.
2. Enumerate only eligible interior physical edges in ascending `(u,v)` order.
3. Stage each hinge and validate topology, affected-valence route coverage,
   material classifications, geometric proof metrics, maximum dihedral, and
   local topology-generation cooldown.
4. Compute a lexicographic score: Delaunay excess, minimum-angle gain,
   minimum-mean-ratio gain, then stable edge IDs. A secondary valence score
   may use the reduction in `sum((valence-6)^2)` for interior vertices, but it
   must never override evaluator coverage.
5. Select a deterministic independent set whose affected two-rings do not
   overlap. Do not mutate topology in an OpenMP candidate loop.
6. Apply the selected batch serially to staged connectivity, rebuild once,
   recompute complete science, then commit or roll back atomically.
7. Increment `topologyGeneration`, invalidate/rebuild all derived state, reset
   optimizer history, and persist the event.

Re-enumerating after each flip is simpler and safer for the first implementation
than batching. A batch should be introduced only after serial semantics are
fixed and tested.

## Focused proof verification

The isolated test was compiled and run under WSL/GCC 15.2 with C++17:

```text
[==========] Running 5 tests from 1 test suite.
[  PASSED  ] 5 tests.
```

The five tests demonstrate:

- acceptance of a clearly improved planar hinge;
- rejection of a cyclic rectangle whose opposite-angle sum is exactly pi;
- strict minimum-angle hysteresis;
- rejection when the proposed diagonal collapses;
- rejection of nonfinite input and invalid options.

No production/CUDA build target or source was changed. The proof header is
unused unless explicitly included, and no production call site includes it.
