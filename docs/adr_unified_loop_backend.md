# ADR: unified irregular Loop backend

Status: preliminary, non-authorizing decision record

Date: 2026-08-05

Package: WP0.1 plus post-merge external-review amendment

Reviewed WP0 aggregate audit base:
`e9af3ddad494fc073040ee82bdf07944b9fee8cf`

Reviewed WP0 aggregate audit endpoint:
`f8e76ea5bb444ba447a5ae9178a309545f2533ba`

Original WP0.1 base:
`906a7850d2c1ceec3ffdda9bf0ce44a437f6aa4a`

Separately inventoried PR 176 stack root:
`46c06080fb663bcb43f38cf32fc1b45daa8732e8`

Separately inventoried PR 182 stack head:
`9587e3dce4509029e611e2937bac570b410193c3`

## Purpose and authority boundary

This ADR records the current implementation facts, proposed architecture, and
questions requiring explicit authority before production work proceeds. It
does not activate a backend, accept a new scientific baseline, change a volume
functional, quarantine the legacy matrix, dispose of the PR 176/182 stack, or
modify CUDA.
The user's instruction to begin preparatory production work authorizes this
inventory and evidence package; it does not implicitly approve D0-D5, D2b, or
D8.

Current main and the PR 176 -> PR 182 stack are different evidence sets. Current main contains
Valence-4 and Valence-5 whole-mesh runtime routes and a Valence-3 proof-only
row provider. PR 176 is the open stack root that would add Valence-3 production
source and routing; PR 182 is its evidence-only leaf, based on PR 176 rather
than `main`. PR 182 is open, green, and mergeable at the SHA above. Its convergence result
is limited to the symmetric and asymmetric `3/4/4` triangular bipyramids,
OpenSubdiv 3.7.0, isolation level 5, nested depths 0 through 4, fixed study
parameters, and its recorded global/force activation targets. It does not
establish a result for other topologies, deeper levels, different rules, or
stock Loop generally. Its dedicated Valence-3 production route is not
current-main production and is not the target architecture of this ADR.

## Decision ledger

The exact status phrases below are checked by
`scripts/inventory_unified_loop_baseline.py`.

| ID | Status | Proposed or existing rule | Required authority / evidence |
| --- | --- | --- | --- |
| D0 | Proposed - pending explicit user stack disposition | Decide PR 176, the production-code root, and PR 182, its negative-evidence leaf, as one stack. Recommended: do not merge PR 176 as a production milestone; extract the symmetric/asymmetric bipyramid fixtures and scoped convergence record before closing or superseding the stack. | Explicit user decision before either PR is merged, closed, retargeted, or extracted. PR 176 is the blocking decision; PR 182 cannot reach `main` independently. |
| D1 | Approved - Stock OpenSubdiv 3.7.0 Loop semantics are the forward-looking CPU proof baseline. Completed rows are not modified to reproduce legacy masks. This does not select Far versus Bfr, does not change the production default, and does not approve arbitrary production inputs. | Stock OpenSubdiv 3.7.0 Loop semantics are the forward-looking CPU proof baseline. Completed rows are not modified to reproduce legacy masks. This does not select Far versus Bfr, does not change the production default, and does not approve arbitrary production inputs. | Explicit user scientific approval on 2026-08-06. Prior acceptance applies only to the narrow Valence-5 lane; D2b still governs the periodic ghost-band representation. |
| D2 | Approved - The initial generic proof scope is complete, closed, consistently oriented, two-manifold triangular meshes. Boundaries, holes, ghosts, non-triangles, non-manifold incidence, and inconsistent orientation must fail before mutation. This does not decide D2b and does not authorize production activation. | The initial generic proof scope is complete, closed, consistently oriented, two-manifold triangular meshes. Boundaries, holes, ghosts, non-triangles, non-manifold incidence, and inconsistent orientation must fail before mutation. This does not decide D2b and does not authorize production activation. | Explicit user approval on 2026-08-06 for the closed-mesh proof scope only. |
| D2b | Proposed - pending explicit user production-scope approval | The primary flat/periodic workload has 2,720 regular physical faces and a 960-face ghost band containing all 336 mixed-valence faces. Recommended: require an explicit periodic/ghost topology, Ptex/source-ID, and physical-face evaluation policy in WP3.2; otherwise declare that workload permanently legacy-only. | Explicit user decision before WP3.2 final scope and before any WP6 production/default claim. |
| D3 | Pending post-WP2.1 oracle, independent scientific review, and user decision | Candidate canonical functional is full-divergence signed volume with exact `1/6` when triangle weights sum to one. | Independent WP2.1 oracle, technical review, independent scientific review, and explicit user baseline decision. |
| D4 | Pending post-WP2.1 characterization, independent scientific review, and user decision | Candidate compatibility behavior is a named `legacy-x-volume` mode that reproduces the x-only literal `0.16666666666`, never selected by valence. Its default, metadata, and retirement date are undecided. | WP2.1 characterization, independent scientific review, and explicit user compatibility decision. |
| D5 | Pending WP1.1a evidence and explicit user approval | Reject the current all-Valence-5 11-control predicate before matrix evaluation or publication. The intended `5/6/6` class has never been admitted by the all-`5/5/5` predicate; implementing it would be net-new work, not retained compatibility, and requires its own reviewed scientific gate. | WP1.1a may remove unconditional undefined behavior without deciding D5. Quarantine of the accepted all-Valence-5 fixture and any new `5/6/6` implementation require explicit user approval after WP1.1a evidence. |
| D6 | Restated existing project policy | Default builds and tests remain OpenSubdiv-free throughout proof and opt-in work. Every OpenSubdiv build remains explicit and requires `OPENSUBDIV_ROOT`. | WP0.1 makes no new decision; later changes require a separate dependency decision. |
| D7 | Restated existing user instruction | WP0-WP7 do not change `src/cuda`, `include/cuda`, CUDA targets, or CUDA scientific baselines. CUDA work is deferred to its backward-compatibility lane. | WP0.1 makes no new decision; expansion requires explicit user authority. |
| D8 | Proposed - pending explicit user performance-budget approval | Freeze the same-binary alternating-order regular benchmark. The `generic_vs_cached_regular_median <= TBD` ceiling remains explicitly pending the named D8 measurement and approval; the candidate direct-route bound is `generic_vs_direct_regular_each_case <= 2.00`. Topology preparation is reported separately and occurs once per epoch. | Reproduce the benchmark protocol, review platform variance, then obtain explicit user approval before WP3.3 performance PASS or WP6 default selection. |
| D12 | Proposed - pending explicit user approval after technical and scientific review | Freeze the B2-readiness preparation-cost, retained-row-memory, process-memory, and threading acceptance criteria plus the complete section-8/section-7 fixture execution manifest. | Separate reviewed preflight before any Bfr/Far candidate run. Approval changes no D10 input, does not decide D9a/D9b, does not decide D8, and does not authorize production. |

D3 and D4 remain pending WP2.1, independent scientific review, and explicit
user decisions. D2b, D5, and D8 also remain pending their named evidence and
authority. They must not be inferred from D1, from the proposed target
architecture, or from the Valence-3 stack's full-divergence implementation.

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

The checked-in primary workload is not one of those closed fixtures:
`data/example/example.params` selects `isFlat=true` and periodic boundaries.
Production characterization records 2,720 regular physical faces plus a
960-face periodic ghost band; all 336 mixed-valence faces lie in that ghost
band. D2 is therefore a closed-proof scope, while D2b determines whether and
how the primary workload crosses the eventual generic production seam.

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
duplicate only at this seam. The WP3.1 representation is sparse at rest:
immutable rows retain original source IDs and coefficients. At evaluation,
one deterministic union source list per face is formed and the requested
sample rows are densified into a compact row-by-union-source matrix for the
existing dense algebra. Complete transactions are validated before the guarded
production write.

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
| Regular geometry | Legacy x-only `0.16666666666 * weight * position.x * cross(du,dv).x`. The decimal literal is the compatibility fact; it is not exact `1/6`. |
| Valence-4 geometry | Same legacy x-only expression. |
| Valence-5 geometry | Same legacy x-only expression. |
| CUDA CPU/device geometry proof | Same legacy x-only expression. |
| Global volume constraint energy | `0.5 * uVol / vol0 * (vol - vol0)^2`. |
| Membrane volume force | Full-vector analytic derivative, scaled by `(uVol/vol0) * (vol-vol0) / 3`. |
| PR 182 Valence-3 stack geometry | Separately stacked full-divergence `1/6 * weight * dot(position,cross(du,dv))`. |

The legacy decimal literal `0.16666666666` and exact `1/6` are distinct
compatibility/scientific baselines. Inventory and migration code must not
normalize one into the other.

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

### Frozen B2p / D10 targets (approved)

B2p froze the following a-priori targets before any B2 candidate run. The user
explicitly approved D10 on 2026-08-08 after that freeze and before B2 began.
Approval accepts the frozen coverage challenge and changes no value. These rows
do not qualify Bfr, decide D9a or D9b, rank Bfr against Far, widen any existing
tolerance, or authorize production.

| Name | Value | Dimension / norm | Rationale | Owning gate |
| --- | ---: | --- | --- | --- |
| `irregular_position_row_accuracy` | `5.0e-6` | Maximum source-union coefficient `l1` and geometry-normalized Cartesian `l-infinity`; position order. | Inherits the already-frozen regular row scale before irregular output exists. | D10 / B2 D9a irregular-oracle gate. |
| `irregular_first_derivative_row_accuracy` | `2.5e-5` | Same paired norms for `du`,`dv`; per canonical parameter. | Fixed upstream derivative-order ratio of five from the existing regular-scale position anchor. | D10 / B2 D9a irregular-oracle gate. |
| `irregular_second_derivative_row_accuracy` | `1.25e-4` | Same paired norms for `duu`,`duv`,`dvv`; per canonical parameter squared. | Fixed second upstream ratio of five, declared before candidate output; applies only at or outside the frozen inner radius. | D10 / B2 D9a irregular-oracle gate. |
| `flip_pair_row_changed_linf` | `1.0e-12` | Absolute coefficient `l-infinity` on the source-ID union, missing coefficient zero. | Locality classifier at the existing invariant scale; explicitly not an accuracy tolerance. | B2 flip-pair locality report. |

For the geometric cross-check, the scale is the finite positive maximum
control-edge length `L_M` computed once per checked-in fixture. Position has
units `L`, first derivatives `L / canonical-parameter`, and second derivatives
`L / canonical-parameter^2`. Position sum one and derivative sum zero retain
their separate existing `1.0e-12` invariant; an invariant cannot satisfy an
accuracy row. Oracle arithmetic, mapping, inner-radius, and coverage rules are
authoritatively specified in section 3.2 of
`docs/bfr_loop_backend_plan_macos.md` and are inventoried with these values.

Proposed D8 performance inputs are frozen as decision inputs, not silently
activated thresholds: `generic_vs_cached_regular_median <= TBD` and
`generic_vs_direct_regular_each_case <= 2.00`, measured as coordinate-only
steady state with the existing same-binary, alternating-order,
warmup-plus-repeat protocol. Topology preparation is reported separately and
occurs once per epoch. The cached-route median remains pending until the named
D8 measurement is reproduced and reviewed
for platform variance. Any numeric ceiling replacing `TBD`, and the direct-route
candidate bound, require explicit approval before they become acceptance gates.

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
| `data/fixtures/candidates/b2p_single_flip_family/base/candidate_metadata.json` | `66c9ab55624afb0f7fc8b444e6e5d9479bde356483bb11a73e0d5c6ce3edd35d` |
| `data/fixtures/candidates/b2p_single_flip_family/base/faces.csv` | `bcc295b8c7e972982676afedb7ead94bbddfd4702f6d638a070630c9f32f7672` |
| `data/fixtures/candidates/b2p_single_flip_family/base/vertices.csv` | `b538595170eca52b4b648cbc3c91e6f63ff6b0a40fc16a6f2a786d5b464c4f52` |
| `data/fixtures/candidates/b2p_single_flip_family/family_metadata.json` | `c8ac7ea89681b72508a29b2bca8f8b97ef2c65acab6aebe19445ae8eb7136fa2` |
| `data/fixtures/candidates/b2p_single_flip_family/flip_000/candidate_metadata.json` | `226312a46cb6f611efa54866b37787a01b68aa783d614936982b407bf0dc55d9` |
| `data/fixtures/candidates/b2p_single_flip_family/flip_000/faces.csv` | `744b5a91acbdf6926890eb378dd7410a580155bd84ffb583c49d63a6a56fca76` |
| `data/fixtures/candidates/b2p_single_flip_family/flip_000/vertices.csv` | `b538595170eca52b4b648cbc3c91e6f63ff6b0a40fc16a6f2a786d5b464c4f52` |
| `data/fixtures/candidates/b2p_single_flip_family/flip_001/candidate_metadata.json` | `b0315a513777cad7fb5f5ba9eed395959e3bce6848283c07cf7d7f0fccde974e` |
| `data/fixtures/candidates/b2p_single_flip_family/flip_001/faces.csv` | `58d78e761bcfb8172eff55084ad99968c14089ba08b2af78f3504ba621c9bc74` |
| `data/fixtures/candidates/b2p_single_flip_family/flip_001/vertices.csv` | `b538595170eca52b4b648cbc3c91e6f63ff6b0a40fc16a6f2a786d5b464c4f52` |
| `data/fixtures/candidates/b2p_single_flip_family/flip_002/candidate_metadata.json` | `a66f2872f64ca861ca6648118aa4981482fc5f247742c5c189ecc906288f934e` |
| `data/fixtures/candidates/b2p_single_flip_family/flip_002/faces.csv` | `7ee844bfaec6aad97892673d63c7a00522e141db3dc707b6615be6852fd83727` |
| `data/fixtures/candidates/b2p_single_flip_family/flip_002/vertices.csv` | `b538595170eca52b4b648cbc3c91e6f63ff6b0a40fc16a6f2a786d5b464c4f52` |
| `data/fixtures/candidates/b2p_valence789/candidate_metadata.json` | `f6a88b98adec1a90f4d591b9711aa20fd724b14755beadf064e42af8328a381b` |
| `data/fixtures/candidates/b2p_valence789/faces.csv` | `bcc295b8c7e972982676afedb7ead94bbddfd4702f6d638a070630c9f32f7672` |
| `data/fixtures/candidates/b2p_valence789/vertices.csv` | `b538595170eca52b4b648cbc3c91e6f63ff6b0a40fc16a6f2a786d5b464c4f52` |
| `data/fixtures/candidates/b2p_adjacent_extraordinary/candidate_metadata.json` | `de6bf74052e24f26049c3d194570a081d47bd5dcd278ad9b34c6b1cf39973d1b` |
| `data/fixtures/candidates/b2p_adjacent_extraordinary/faces.csv` | `1ecbe26328311f99b2e55ccdc7e1d614947099fe1fff124cfca83dc62f5dddbb` |
| `data/fixtures/candidates/b2p_adjacent_extraordinary/vertices.csv` | `b650ff4c1aed263701d25305d846f520933a2deb457655558f17a855e65c88b7` |
| `data/fixtures/candidates/b2_readiness_v1/asymmetric_344_bipyramid/candidate_metadata.json` | `e92b244806eaecd9230a3f3f9977f61ddeff3875ee6550c2dfbdb211a8e05e04` |
| `data/fixtures/candidates/b2_readiness_v1/asymmetric_344_bipyramid/faces.csv` | `c621d95a16a6915ab443bf74f162bddde96a85ee82e06152cbef82f28ef87486` |
| `data/fixtures/candidates/b2_readiness_v1/asymmetric_344_bipyramid/vertices.csv` | `b275aac1d1b422a131c3703eb7f56fd4d5bf21230b277835774bc27405d10a4e` |
| `data/fixtures/candidates/b2_readiness_v1/closed_566_refined_icosahedron/candidate_metadata.json` | `f974fb5bb1d542561672c1e7d2d52bf5220acc09dd3b5510dc14f1d98343b0b5` |
| `data/fixtures/candidates/b2_readiness_v1/closed_566_refined_icosahedron/faces.csv` | `d72e02a882c536643e8a3405efe8bb32c745bc034cbc55dcc1af0d5eba11e1b8` |
| `data/fixtures/candidates/b2_readiness_v1/closed_566_refined_icosahedron/vertices.csv` | `cb6c618c254b36bbe27ff354f5dc009222e95277188833a3385a4f3c378b0bd6` |
| `data/fixtures/candidates/b2_readiness_v1/execution_manifest.json` | `bdadac60281c0430789e079cefb819c0c8e127899d4ede4ba7227d233452a07b` |
| `data/fixtures/candidates/b2_readiness_v1/regular_all6_torus/candidate_metadata.json` | `11aba5339fced78cab1056b99d03766ecf3b0a7178e1c04c5376f1af01f2cf1c` |
| `data/fixtures/candidates/b2_readiness_v1/regular_all6_torus/faces.csv` | `7797a1ded38d99e83707fb85e23a2a193c5857f7425a5f678ceccb1506c67cd0` |
| `data/fixtures/candidates/b2_readiness_v1/regular_all6_torus/vertices.csv` | `923914e925eaf0f60eb9a087f0150ad37b9e56bf0191ffc52b5d7fbd91b2903c` |
| `data/fixtures/candidates/b2_readiness_v1/symmetric_344_bipyramid/candidate_metadata.json` | `6afd2ec0c0df1cd71a8597fa78889dbf9daea9627d10b97165acec1cd39f9cb0` |
| `data/fixtures/candidates/b2_readiness_v1/symmetric_344_bipyramid/faces.csv` | `c621d95a16a6915ab443bf74f162bddde96a85ee82e06152cbef82f28ef87486` |
| `data/fixtures/candidates/b2_readiness_v1/symmetric_344_bipyramid/vertices.csv` | `bbce1680eb4006622e14dd5d724134df826471bb55e0332c19a208b5e92429a5` |

### Pending D12 B2-readiness ledger

D12 is a pre-result proposal. It freezes operational fail-stop criteria for the
small B2 proof corpus; it does not assert production performance. On the
reference dedicated Apple-silicon macOS platform and the exact section 3.4
protocol in `docs/bfr_loop_backend_plan_macos.md`:

| Name | Pending value | Unit / aggregation |
| --- | ---: | --- |
| `b2_preparation_median_ms` | `1000.000` | Upper bound on the eighth sorted value of 15 monotonic-wall-time measurements after 3 warmups, per candidate/fixture/level/cache-mode case. |
| `b2_preparation_single_run_failstop_ms` | `10000.000` | Upper bound on every one of the 15 measured repeats; timeout or missing repeat fails. |
| `b2_retained_row_payload_bytes_per_face` | `131072` | Per-face upper bound on the exact Bfr-plan section 3.4 logical six-row retained payload; its formula includes the source ID repeated in every sparse-row coefficient entry. The exact schema-2 corpus/sample-policy dense bound is 105,444 bytes. |
| `b2_preparation_peak_rss_delta_mib` | `64.000` | Upper bound on the maximum macOS resident-size delta across every named boundary in all 3 warmup plus 15 measured repeats, divided by 1048576; the baseline is sampled once post-parse/pre-refiner. |

The numeric physical fingerprint is macOS `26.5.1` build `25F80`, `arm64`,
`Mac17,2`, `Apple M5`, 25,769,803,776 bytes, 10 physical/logical cores, and
perflevel logical counts 4 and 6. Compiler identity is Apple clang 21.0.0
(`clang-2100.1.1.101`) at the CommandLineTools `clang++` path. The manifest
freezes exact Release flags, OpenSubdiv 3.7.0 and MPFR 4.2.2 pins, AC/nominal
thermal checks, `mach_continuous_time`, and the complete fresh-process and RSS
lifecycle. GitHub-hosted `macos-26` remains correctness/dependency audit only;
numeric evidence must be an independently reviewed exact-head local artifact
from this physical host.

The same hash freezes a fail-closed OpenSubdiv build: clean tag commit
`9dab8a47bfbb1388ec8388fe61f5f916e6123f38`, CMake 4.4.2 with Unix
Makefiles, exact options and Release/TSan flags, only target `osd_static_cpu`,
and its exact ordered 47 translation units/object members. Release and TSan
roots are disjoint. Exact commands, compile database, link script, member list,
per-source hashes and commands, archive hashes, and proof link/dependency
evidence are mandatory; any mismatch is `BUILD_PROVENANCE_FAILURE` and cannot
produce B2 evidence.

Candidate Release warnings remain fail-closed with `-Werror`; the pinned
third-party archive omits those diagnostic-policy flags while retaining the
same numerical/toolchain flags. Raw Apple archives contain exactly one leading
`__.SYMDEF` symbol-table member plus the 47 frozen objects.

The exact sweeps are Bfr smooth levels `2,3,4,5,6,7,8` with sharp level `6`
and Far isolation levels `2,3,4,5,6,7,8`; their integers are not commensurable.
Bfr cost/RSS covers cache-disabled and serial-cache modes; Far has one uncached
proof-only mode. Bfr threading expands every unique valid fixture identity over
both cache-disabled and threaded-cache modes, all seven levels, workers
`1,2,4`, and 20 rounds using shared refiner/factory/cache state. A fully
instrumented threaded-cache `UNQUALIFIED` leaves D9a evidence incomplete. A
detected cache race is `UNSUPPORTED/BLOCKING`; only a complete mandatory
serial/cache-disabled PASS may support a separately reviewed **serial-only**
D9a proposal. This ledger does not infer D9a.

The hash-covered schema-2 execution ledger is
`data/fixtures/candidates/b2_readiness_v1/execution_manifest.json`, canonical
contract SHA-256
`30db9a564c165c2f04125f25a983df6301225ca4355386bf5c91a500ea67f368`.
Exactly 14 ordered unified-plan section 8 entries precede exactly three Bfr-plan
section 7 entries. Per-row executable procedures or scoped `N/A` reasons,
aliases, unique byte-evidence groups, face/corner/sample/row order, exact
binary64 mutation bits, numeric applicability, platform/build, aggregation,
RSS, and threading are all part of that hash. D12 remains pending explicit user
approval after technical and scientific review. Approval changes no existing
D10 value, fixture, oracle contract, metadata, or hash and does not decide
D9a/D9b or D8.

The schema-2 proof-sample `weight` is exact binary64 positive one solely to
satisfy the merged B1 positive-weight validator. It is forbidden as a
quadrature or integration weight; D12 does not select quadrature.

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
   inventory at the exact PR head; their PASS validates evidence completeness
   but does not decide D0-D5, D2b, or D8.
2. D1 and D2 were explicitly approved by the user on 2026-08-06 with the
   proof-only scope limits recorded above. D0 remains pending explicit user
   stack disposition; D2b and D8 remain named production/performance choices.
   D6 and D7 remain existing constraints.
3. WP1.1a unconditional safety work and WP2.1 characterization may proceed.
   WP1.1b remains blocked on WP1.1a evidence and D5; neither package decides
   D3/D4.
4. D3/D4 remain blocked until WP2.1, independent scientific review, and the
   named explicit user decisions.
5. WP3 closed proofs may proceed under the approved D1 and D2 proof-only scope.
   WP3.2 production-scope completion additionally requires D2b; performance
   PASS requires D8.
6. Any changed source anchor, fixture byte, tolerance, selector, functional
   name, output/checkpoint contract, or follow-up commit invalidates the
   inventory/review and requires a new exact-head run.

Verification for this package is V0 only: Python compilation, inventory
`--check --json`, focused mutation tests, and `git diff --check`. Passing V0
means the baseline was recorded consistently. It does not grant any production
or scientific decision.
