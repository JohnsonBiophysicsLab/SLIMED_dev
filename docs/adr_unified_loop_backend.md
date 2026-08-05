# ADR: unified irregular Loop backend

Status: preliminary, non-authorizing decision record

Date: 2026-08-05

Package: WP0.1

Authoritative current-main base:
`906a7850d2c1ceec3ffdda9bf0ce44a437f6aa4a`

Separately inventoried PR 182 stack head:
`9587e3dce4509029e611e2937bac570b410193c3`

## Purpose and authority boundary

This ADR records the current implementation facts, proposed architecture, and
questions requiring explicit authority before production work proceeds. It
does not activate a backend, accept a new scientific baseline, change a volume
functional, quarantine the legacy matrix, dispose of PR 182, or modify CUDA.
The user's instruction to begin preparatory production work authorizes this
inventory and evidence package; it does not implicitly approve D0-D5.

Current main and PR 182 are different evidence sets. Current main contains
Valence-4 and Valence-5 whole-mesh runtime routes and a Valence-3 proof-only
row provider. PR 182 is open, green, and previously reviewed as mergeable at
the SHA above, but it is stacked on a non-main ancestry. Its deeper bipyramid
study is useful negative convergence evidence. Its dedicated Valence-3
production route is not current-main production and is not the target
architecture of this ADR.

## Decision ledger

The exact status phrases below are checked by
`scripts/inventory_unified_loop_baseline.py`.

| ID | Status | Proposed or existing rule | Required authority / evidence |
| --- | --- | --- | --- |
| D0 | Proposed - pending explicit user disposition | Do not merge PR 182 as a production milestone; preserve or extract only clearly labelled negative convergence evidence. | User decision before PR closure, retargeting, or evidence extraction. |
| D1 | Proposed - pending explicit user scientific approval | Use stock OpenSubdiv Loop semantics as the forward-looking CPU baseline. Do not modify completed rows to imitate the legacy mask. | Explicit user scientific approval. Prior acceptance applies only to the narrow Valence-5 lane. |
| D2 | Proposed - pending explicit user/maintainer approval | Initial generic scope is a complete closed, consistently oriented, two-manifold triangular mesh. Reject boundaries, holes, ghosts, non-triangles, non-manifold incidence, and inconsistent orientation before mutation. | Explicit user/maintainer approval before WP3. |
| D3 | Pending post-WP2.1 oracle, scientific review, and user decision | Candidate canonical functional is full-divergence signed volume with exact `1/6` when triangle weights sum to one. | Independent WP2.1 oracle, technical review, scientific review, and explicit user baseline decision. |
| D4 | Pending post-WP2.1 characterization and user/maintainer decision | Candidate compatibility behavior is a named `legacy-x-volume` mode, never selected by valence. Its default, metadata, and retirement date are undecided. | WP2.1 characterization and explicit user/maintainer compatibility decision. |
| D5 | Proposed - pending explicit user approval | Reject the current all-Valence-5 11-control predicate before matrix evaluation or publication. Retain a 5/6/6 compatibility path only if its topology, ordering, and distinct controls are independently proven. | Explicit user approval because quarantine reverses a previously positive compatibility fixture. |
| D6 | Accepted existing policy | Default builds and tests remain OpenSubdiv-free throughout proof and opt-in work. Every OpenSubdiv build remains explicit and requires `OPENSUBDIV_ROOT`. | Existing project policy; later changes require a separate dependency decision. |
| D7 | Accepted existing user instruction | WP0-WP7 do not change `src/cuda`, `include/cuda`, CUDA targets, or CUDA scientific baselines. CUDA work is deferred to its backward-compatibility lane. | Existing user instruction; expansion requires explicit user authority. |

D3 and D4 remain pending post-WP2.1. They must not be inferred from D1, from
the proposed target architecture, or from the Valence-3 stack's full-divergence
implementation.

## Context: current-main implementation facts

### Build and runtime selection

Current main has three Makefile opt-ins:

- `USE_OPENSUBDIV_REGULAR`;
- `USE_OPENSUBDIV_VALENCE3`; and
- `USE_OPENSUBDIV_VALENCE5`.

All three require an explicit `OPENSUBDIV_ROOT`. Valence 4 has no independent
Makefile flag: its provider is compiled under `USE_OPENSUBDIV_REGULAR`. The
source-level runtime selectors are:

- `SLIMED_USE_OPENSUBDIV_REGULAR`, using broad truthy semantics except empty,
  `0`, `false`/`FALSE`, and `off`/`OFF`;
- `SLIMED_USE_OPENSUBDIV_VALENCE4=1` exactly;
- `SLIMED_USE_OPENSUBDIV_VALENCE5=1` exactly; and
- proof selector `SLIMED_USE_OPENSUBDIV_VALENCE5_PHASE2=1` exactly.

There is no current-main Valence-3 runtime selector. The top-level evaluator
rejects simultaneous Valence-4 and Valence-5 production requests and returns
after either accepted extraordinary whole-mesh route. Those are exclusive
fixture routes, not mixed-topology face dispatch.

The inventory fails closed if another Makefile/runtime OpenSubdiv selector or
named volume-factor/mode token appears without this ADR and its allowlists
being reviewed together.

### Exact topology guards and the legacy mismatch

The accepted exact identities are binding compatibility facts:

| Lane | Exact identity | Additional guard |
| --- | --- | --- |
| Valence 3 proof | 4 vertices, 4 oriented faces, every source valence 3 | Stable source/face indices, closed physical faces, empty production one-ring. |
| Valence 4 runtime | 6 vertices, 8 oriented octahedron faces, every source valence 4 | Exact face order/orientation, original-source coverage 0..5, closed physical faces, empty production one-ring. |
| Valence 5 runtime | 12 vertices, 20 oriented icosahedron faces, every source valence 5 | Exact face order/orientation, nine exact sources per face, closed physical faces. |

The precise oriented face arrays are emitted in the machine-readable
inventory and bound to the fixture hashes below. Face reversal, face
reordering, count changes, valence changes, and one-ring drift are rejection
cases, not equivalent fixtures.

The legacy 11-control setup predicate currently admits faces whose three
corner valences are 5/5/5. The matrix construction describes one valence-5
corner and two valence-6 corners (5/6/6). The predicate also declares `d4`,
`d7`, and `d8` before branches intended to identify the extraordinary corner.
This is a confirmed topology/implementation mismatch. D5 governs changing
it; WP0.1 only records it.

### OpenSubdiv provider policy

All three exact providers request stock `Sdc::SCHEME_LOOP` and
`VTX_BOUNDARY_EDGE_ONLY`. Only the Valence-3 provider compile-pins
`OPENSUBDIV_VERSION_NUMBER == 30700`. Valence 4 and Valence 5 do not compile-
pin or report an equivalent qualification. Therefore the current inventory
does not claim that arbitrary ambient OpenSubdiv versions are qualified.

D1 proposes one future OpenSubdiv 3.7 policy, one dependency gate, and one
full-mesh provider. It rejects these alternatives:

- another custom extraordinary mask;
- post-processing stock rows to mimic the legacy Warren-style matrix;
- continuing per-valence providers as the generic production architecture;
- selecting a scheme or functional independently for individual faces.

These alternatives are rejected architecturally, but D1 still requires the
explicit scientific approval shown in the ledger.

### Cache and source-keyed compatibility seam

Only the regular OpenSubdiv evaluator currently has the reviewed mutable
row-table cache. Its schema-1 identity includes OpenSubdiv version, Loop and
boundary options, adaptive depth, derivative requests, scalar width, row
tolerance, topology and face tags, one-ring state, `VWU`, quadrature
coefficients, and shape functions. Coordinates are intentionally excluded.
The cache is mutex guarded. Explicit invalidation exists only in
`Mesh::setup_from_vertices_faces()` and `Mesh::setup_flat()`.

The existing backend-neutral `Source_keyed_kernel_call` is reusable evidence:
source IDs are variable-cardinality original mesh IDs and are range, uniqueness,
cardinality, and finiteness checked. Its compatibility sample still contains
seven derivative rows. Rows 5 and 6 must be exactly equal duplicated mixed
derivatives. The future generic backend should store one mixed derivative and
duplicate only at this seam. Complete transactions are validated before the
guarded production write.

The future topology-epoch cache must expand the identity and invalidation
contract before production use: complete connectivity and orientation,
boundary/hole/ghost policy, Loop options, fixed quadrature policy, OpenSubdiv
version, and every row-affecting tag belong in the key; setup, remeshing,
accepted edge flips, orientation changes, and topology-tag changes must use
one reviewed invalidation mechanism.

### Volume functional inventory

The current implementation is not one functional and must not be described as
one:

| Consumer | Current-main behavior |
| --- | --- |
| Regular geometry | Legacy x-only `1/6 * weight * position.x * cross(du,dv).x`. |
| Valence-4 geometry | Same legacy x-only expression. |
| Valence-5 geometry | Same legacy x-only expression. |
| CUDA CPU/device geometry proof | Same legacy x-only expression. |
| Global volume constraint energy | `0.5 * uVol / vol0 * (vol - vol0)^2`. |
| Membrane volume force | Full-vector analytic derivative, scaled by `(uVol/vol0) * (vol-vol0) / 3`. |
| PR 182 Valence-3 stack geometry | Separately stacked full-divergence `1/6 * weight * dot(position,cross(du,dv))`. |

Geometry, energy, and force anchors are inventoried independently so a shared
name or coefficient cannot hide their mismatch. WP2.1 must characterize
translation, orientation, rigid motion, net force/torque, zero-penalty, and
per-source/per-axis finite differences before D3 or D4 is decided.

## Frozen tolerance and fixture ledger

WP0.1 freezes existing facts; it does not declare these tolerances appropriate
for the future generic backend.

| Name | Value | Current owner |
| --- | ---: | --- |
| `regular_row_and_route_parity` | `5.0e-6` | Regular evaluator row and route checks. |
| `regular_residual_scale_floor` | `1.0e-12` | Regular normalized residual denominator. |
| `valence3_row_invariants` | `1.0e-12` | Valence-3 proof row sums. |
| `valence4_row_invariants` | `1.0e-12` | Valence-4 exact provider row sums (literal). |
| `valence5_row_invariants` | `1.0e-12` | Valence-5 exact provider row sums. |
| `valence5_reviewed_production_parity` | `1.0e-10` | Valence-5 reviewed face/force parity. |
| `irregular_serial_openmp_envelope` | `1.0e-10` | Existing irregular scalar/force reduction characterization. |

Authoritative fixture hashes:

| Fixture file | SHA-256 |
| --- | --- |
| `data/fixtures/candidates/closed_valence3_tetrahedron/candidate_metadata.json` | `3b2cf28dd5b4b52ea5a999e07fc89527513066ac8f2ef20b52137448fcb52660` |
| `data/fixtures/candidates/closed_valence3_tetrahedron/faces.csv` | `acfbd18a1922e465052f6badf5aa2567faa282add3edc7867f3bca7493e6e1aa` |
| `data/fixtures/candidates/closed_valence3_tetrahedron/vertices.csv` | `4a82e312830953d67731970042f5cf7d174e6af9f8844b7cd2b321209e51b898` |
| `data/fixtures/candidates/closed_valence4_octahedron/candidate_metadata.json` | `2109779d724d924ac416a127fa4a376cf1a72fbe9fa1391223995ebbccb60b74` |
| `data/fixtures/candidates/closed_valence4_octahedron/faces.csv` | `af9742137b89c25cc29e8b60e137967d8adfcdd80f33d3172fc13f1ed93838e8` |
| `data/fixtures/candidates/closed_valence4_octahedron/vertices.csv` | `b650ff4c1aed263701d25305d846f520933a2deb457655558f17a855e65c88b7` |
| `data/fixtures/closed_valence5/faces.csv` | `561b3ec0c4aa6b1e684ef87c2738d8c20a474225bd4960a4a672d306a3e70327` |
| `data/fixtures/closed_valence5/vertices.csv` | `d0dae733433503f9e2aba4f8eda80fa2d6842d0f5a7b922d7ffce158f505cb45` |
| `data/fixtures/candidates/closed_mixed_valence345/candidate_metadata.json` | `74ae00951e6ea20021722a45a887d0c47530d4d7248cb69f553cb1a66a60f14b` |
| `data/fixtures/candidates/closed_mixed_valence345/faces.csv` | `bc1db1bf7fb29e4e4bc7b41f93ea9c206fe80a022736f1f02d22063c0b800233` |
| `data/fixtures/candidates/closed_mixed_valence345/vertices.csv` | `affa93eec68b8de9d5dcd12d31bf1d7222410722b0cca44c58495c558e3d7287` |

Expected scientific values stored with a fixture are regression locks only.
They cannot be the sole WP2 or quadrature oracle.

## Output, checkpoint, and compatibility contract

The reusable energy CSV field order is ten channels: curvature, area, volume,
thickness, tilt, regularization, harmonic bond, Gag scaffolding, idealized
protein lattice, and total. `EnergyForce.csv` appends mean force. Output uses
round-trip-safe precision 17.

Restart writes use tag `SLIMED_RESTART_V2`, precision 17, the current ordered
optimization/thermal/mesh/record fields, a `.tmp` file, and atomic rename to
the destination. The current CSV and restart schemas contain no backend or
volume-functional metadata. WP0.1 does not add any. Later compatibility-mode
metadata requires a schema-compatible design and C4 review; it cannot be
claimed present now.

Legacy exact routes have no implicit lifetime extension. They remain unchanged
until D5 and later migration gates decide quarantine, explicit compatibility,
and eventual retirement. No old valence environment variable may become a
silent alias for a different scheme or functional.

## Deferred lanes

`Adaptive_edge_flip_quality.hpp` is a proof-only quality predicate. It has no
production call site and no runtime selector. Edge flipping remains deferred
until topology epochs, invalidation, state transfer, energy discontinuity,
rollback, and topology safety have their own reviewed package.

CUDA remains frozen under D7. The inventory reads its current x-only geometry
anchors to characterize compatibility but makes no CUDA edit.

## Execution gates after WP0.1

1. Technical and scientific reviewers verify this ADR and the fail-closed
   inventory at the exact PR head.
2. The user explicitly decides D0 and approves or rejects D1, D2, and D5.
   D6 and D7 remain existing constraints.
3. WP1 may start only after D5. WP2.1 characterization may proceed without
   deciding D3/D4.
4. D3/D4 remain blocked until WP2.1, independent scientific review, and the
   named user/maintainer decisions.
5. WP3 and later generic-backend packages remain blocked until D1 and D2.
6. Any changed source anchor, fixture byte, tolerance, selector, functional
   name, output/checkpoint contract, or follow-up commit invalidates the
   inventory/review and requires a new exact-head run.

Verification for this package is V0 only: Python compilation, inventory
`--check --json`, focused mutation tests, and `git diff --check`. Passing V0
means the baseline was recorded consistently. It does not grant any production
or scientific decision.
