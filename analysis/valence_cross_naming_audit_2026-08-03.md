# Valence 4/5 cross-naming and role audit

Date: 2026-08-03

## Decision

Do **not** directly rename `Valence5_opensubdiv_face_loop.cpp` to match
`Valence4_face_loop_route_preflight.cpp`, or vice versa. The files overlap at
the final production-route layer, but they are not architectural equivalents.

- `Valence4_face_loop_route_preflight.cpp` is a 1,880-line historical
  aggregation. It contains topology preflight, caller-owned row validation,
  geometry staging, scientific evaluation, several publication experiments,
  a production-caller shadow, the guarded production face-loop caller, and the
  runtime-selected route.
- `Valence5_opensubdiv_face_loop.cpp` is a 719-line production-transaction
  implementation. It validates quadrature and provider output, stages geometry,
  performs a scientific dry run, invokes the shared source-keyed production
  seam, verifies postconditions, and exposes Phase 2 and production-route entry
  points.

The genuinely equivalent public operations are only the runtime request query
and final production-route evaluator:

| Valence 4 | Valence 5 | Equivalence |
|---|---|---|
| `opensubdiv_valence4_production_routing_requested()` | `opensubdiv_valence5_production_routing_requested()` | Same role and already uniformly named |
| `evaluate_guarded_valence4_opensubdiv_production_route(Mesh&)` | `evaluate_guarded_valence5_production_route(Mesh&)` | Same role; Valence 5 omits `opensubdiv` from the function name |
| `evaluate_guarded_valence4_opensubdiv_production_face_loop_caller(...)` | private `evaluate_guarded_valence5_face_loop(...)` | Similar orchestration core, but not public-contract equivalents |
| `Valence4OpenSubdivProductionFaceLoopCallerResult` | `Valence5Phase2Result` | Similar result payload at the final route, but both names expose development history rather than stable role |

No source rename is justified in this audit. A direct move would conceal the
Valence 4 monolith instead of correcting it, and would break path-based
inventory evidence. Exact-path searches currently find 25 repository files
that refer to each Valence 4 preflight path, versus three for each Valence 5
face-loop path. The Makefile also discovers every `src/**/*.cpp` by basename,
so an incremental split must avoid duplicate translation-unit basenames and
duplicate definitions.

## Evidence from the current implementation

### Final routes are peers

`Mesh::Compute_Energy_And_Force()` queries both runtime gates together and
rejects a simultaneous request. It then calls one final evaluator and returns:

- Valence 5: `evaluate_guarded_valence5_production_route(*this)`;
- Valence 4: `evaluate_guarded_valence4_opensubdiv_production_route(*this)`.

Both successful paths use the same
`guarded_source_keyed_face_loop::execute_guarded_source_keyed_production_face_loop`
seam and shared production completion. Both leave production one-rings empty.
This final-route pair, rather than the two whole source files, is the correct
naming comparison.

### Row providers are already substantially uniform

The provider layer has the strongest naming alignment:

| Role | Valence 4 | Valence 5 |
|---|---|---|
| Files | `OpenSubdiv_valence4_row_provider.{hpp,cpp}` | `OpenSubdiv_valence5_row_provider.{hpp,cpp}` |
| Namespace | `slimed::opensubdiv_valence4` | `slimed::opensubdiv_valence5` |
| Request | `OpenSubdivValence4RowProviderRequest` | `OpenSubdivValence5RowProviderRequest` |
| Result | `OpenSubdivValence4RowProviderResult` | `OpenSubdivValence5RowProviderResult` |
| Builder | `build_guarded_opensubdiv_valence4_rows` | `build_guarded_opensubdiv_valence5_rows` |

Only field vocabulary differs. Valence 4 uses
`reviewerApprovedExplicitRequest`, `exactSourceCoverageValidated`, and
`productionOneRingsPopulated`; Valence 5 uses
`phase1ProviderExplicitRequest`, `exactNineSourceCoverageValidated`, and
`productionOneRingsMutated`. These should converge on the Valence 4 vocabulary:

- `reviewerApprovedExplicitRequest` describes policy without freezing a phase;
- `exactSourceCoverageValidated` is usable for any source cardinality;
- `productionOneRingsPopulated` describes the state being asserted, while
  `Mutated` is ambiguous about whether entries were added or removed.

Valence 4 factors its topology/source contract into
`Valence4_topology_source_mapping.{hpp,cpp}`. Valence 5 embeds the corresponding
exact topology identity and nine-source aggregation inside its row provider.
Those implementations perform analogous validation, but the files are not yet
nameable peers. A Valence 5 topology/source-mapping extraction should precede
uniform topology-module naming.

### Shared production seam is already the right abstraction

`Guarded_source_keyed_production_face_loop.hpp` is topology-independent and is
used directly by Valence 5. Valence 4 retains
`Valence4_production_face_loop.hpp` as a typed adapter from its older staging
types into that generic seam. This wrapper is not evidence that Valence 5 needs
a parallel file. The preferred direction is to retire the Valence 4-only
adapter after its callers use `GuardedFaceGeometry` and
`PreparedSourceKeyedKernelCall` directly.

## Uniform naming matrix

Use role-first stems while keeping the repository's established capitalization
style. `<N>` below is the valence number.

| Architectural role | Canonical file stem | Canonical namespace | Canonical API/type pattern |
|---|---|---|---|
| Exact topology/source contract | `Valence<N>_topology_source_mapping` | `slimed::valence<N>_topology` | `build_guarded_valence<N>_topology_source_mapping` |
| OpenSubdiv row generation | `OpenSubdiv_valence<N>_row_provider` | `slimed::opensubdiv_valence<N>` | `OpenSubdivValence<N>RowProviderRequest/Result`, `build_guarded_opensubdiv_valence<N>_rows` |
| Source-keyed scientific transaction, if a valence-specific module remains necessary | `Valence<N>_source_keyed_face_loop_transaction` | `slimed::valence<N>_face_loop` | `Valence<N>SourceKeyedFaceLoopRequest/Result`, `evaluate_guarded_valence<N>_source_keyed_face_loop` |
| Runtime-selectable OpenSubdiv route | `Valence<N>_opensubdiv_production_route` | `slimed::opensubdiv_valence<N>_route` | `Valence<N>OpenSubdivProductionRouteResult`, `opensubdiv_valence<N>_production_routing_requested`, `evaluate_guarded_valence<N>_opensubdiv_production_route` |
| Topology-independent validated execution | `Guarded_source_keyed_production_face_loop` | `slimed::guarded_source_keyed_face_loop` | Keep current generic names |

The route name deliberately includes both `opensubdiv` and `production_route`.
`face_loop` alone is too broad: the file also owns dependency/topology gates,
geometry staging, publication, production completion, and postconditions.
`phase2`, `phase3`, `preflight`, `caller`, and `shadow` should remain names for
historical/experimental boundaries, not the stable production route.

### Concrete legacy-to-canonical mapping

| Existing name | Canonical name | Compatibility action |
|---|---|---|
| `Valence4_face_loop_route_preflight.hpp/.cpp` | Split final-route portion into `Valence4_opensubdiv_production_route.hpp/.cpp`; retain preflight-only APIs under the old stem initially | Old header forwards/includes canonical route declarations; old preflight definitions remain until split tests pass |
| `Valence5_opensubdiv_face_loop.hpp/.cpp` | `Valence5_opensubdiv_production_route.hpp/.cpp` | Keep old header as forwarding include; move definitions once path-based inventories are updated |
| `slimed::valence4_route_preflight` final-route members | `slimed::opensubdiv_valence4_route` | Provide `using` declarations or forwarding wrappers in the old namespace |
| `slimed::opensubdiv_valence5_phase2` final-route members | `slimed::opensubdiv_valence5_route` | Preserve Phase 2 endpoint in its legacy namespace; expose the production endpoint through the canonical namespace |
| `Valence4OpenSubdivProductionFaceLoopCallerResult` | `Valence4OpenSubdivProductionRouteResult` | Introduce a type alias during migration |
| `Valence5Phase2Result` when returned by the production route | `Valence5OpenSubdivProductionRouteResult` | Introduce a type alias first; later separate Phase 2-only flags from route result |
| `evaluate_guarded_valence5_production_route` | `evaluate_guarded_valence5_opensubdiv_production_route` | Add canonical wrapper first; retain old function indefinitely or through a documented deprecation window |

## Compatibility-preserving migration plan

1. **Freeze behavior with route-contract tests.** Add a compact cross-valence
   test that checks default-off behavior, exact opt-in names, dependency-disabled
   rejection before mutation, mutual exclusion in the default evaluator, empty
   one-rings, finite output, and the common result flags. Do not use filename
   text inventories as the only proof.

2. **Introduce canonical route headers without moving definitions.** Add
   `Valence4_opensubdiv_production_route.hpp` and
   `Valence5_opensubdiv_production_route.hpp`. Initially they may re-export the
   current functions/types. Existing includes and mangled definitions remain
   intact, so downstream source and binary compatibility are preserved.

3. **Add the one missing canonical function.** Define
   `evaluate_guarded_valence5_opensubdiv_production_route(Mesh&)` as a forwarding
   wrapper to `evaluate_guarded_valence5_production_route(Mesh&)`. Update the
   default evaluator to use the canonical name only after tests cover both.

4. **Normalize provider request/result vocabulary with aliases or accessor
   methods first.** Do not rename public data members in place. Aggregate
   initialization and direct field access make such a rename source-breaking.
   New code should use canonical accessors; the old fields can be removed only
   in a deliberate API-breaking release.

5. **Split Valence 4 by role.** Move only the code reachable from
   `evaluate_guarded_valence4_opensubdiv_production_route` into the canonical
   route translation unit. Keep experimental preflight/staging/publication APIs
   in the old file. Avoid compiling old and new definitions simultaneously;
   the Makefile automatically compiles all `.cpp` files it finds.

6. **Extract Valence 5 topology/source mapping.** Create
   `Valence5_topology_source_mapping.{hpp,cpp}` with a contract parallel to
   Valence 4, then have the Valence 5 row provider consume it. This makes the
   topology naming matrix real rather than cosmetic and gives Valence 3 a
   consistent model.

7. **Converge route internals on shared transaction types.** Replace the
   Valence 4-specific geometry adapter with `GuardedFaceGeometry` and the shared
   prepared-call type. Retain valence-specific topology, sample-count, source
   coverage, and scientific gates outside the generic executor.

8. **Move implementations and update inventories last.** Once semantic tests
   pass, move the Valence 5 implementation and the final Valence 4 route into
   their canonical files. Leave forwarding headers at the old include paths.
   Convert inventory scripts from exact old-path assertions to canonical API
   and behavior assertions.

## Work deliberately not performed

No `.cpp`, `.hpp`, Makefile, test, experiment, script, or CUDA file was changed.
Even a compatibility wrapper would currently overlap the Valence 4 and Valence
5 implementation work occurring in parallel, while a direct file rename would
cause high-churn failures in path-based inventories without improving role
separation. The bounded safe action is this migration specification, followed
by the test-first sequence above.
