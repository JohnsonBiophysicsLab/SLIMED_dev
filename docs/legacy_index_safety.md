# WP1.1a legacy index safety

Status: WP1.1a implementation evidence for checkpoint KL1. This note does not
decide D5, quarantine an accepted fixture, add `5/6/6`, or authorize a route,
formula, baseline, or dependency change.

## Safety boundary

`Mesh::classify_legacy_one_ring()` is a const, observational classifier. For
each face it reports:

- the three corner adjacent-vertex valences;
- the three corner adjacent-face cardinalities;
- every adjacent-face-count candidate and the selected extraordinary corner,
  or sentinel `-1` when there is no unique/current-compatibility selection;
- repeated source IDs in a completely assembled one-ring;
- whether all required opposite-node assignments were unique; and
- staged orientation and one-ring values only after every lookup succeeds.

The result always carries a `LegacyOneRingReasonCode`; no classification is a
bare boolean. The machine-readable names and their effects are:

| Name | Effect |
| --- | --- |
| `READY_REGULAR` | Publish the staged 12 entries after every face is classified. |
| `READY_ALL_VALENCE_FIVE_ALIASED` | Publish the historical 11 entries, including diagnosed aliases, after every face is classified. |
| `SKIPPED_GHOST_FACE` | Preserve both face vectors. |
| `UNSUPPORTED_CORNER_VALENCE` | Preserve both face vectors; this includes `5/6/6`. |
| `INVALID_FACE_CORNER_COUNT` | Reject before publication. |
| `INVALID_CORNER_VERTEX_INDEX` | Reject before dereferencing a face corner. |
| `NO_ADJACENT_FACE_COUNT_MATCH` | Reject before using sentinel `d4/d7/d8`. |
| `AMBIGUOUS_ADJACENT_FACE_COUNT_MATCH` | Reject the malformed two-candidate state. |
| `ADJACENT_VERTEX_FACE_CARDINALITY_MISMATCH` | Report the single-candidate all-valence-5 mismatch and publish its historically assigned 11 entries after every face is classified. |
| `INVALID_ADJACENT_VERTEX_INDEX` | Reject before dereferencing a staged opposite-node source. |
| `OPPOSITE_NODE_MISSING` | Reject instead of storing `-1`. |
| `OPPOSITE_NODE_AMBIGUOUS` | Reject instead of selecting one of multiple source IDs. |

`set_one_ring_vertices_sorted()` first classifies every face. A rejection is
raised before any write to any `Face::adjacentVertices` or
`Face::oneRingVertices`. Ready vectors are then published with non-throwing
vector swaps. Thus a later malformed face cannot leave an earlier face partly
updated. `find_opposite_node_index()` retains its search and `-1` return, but
its missing-node message is now emitted only when `VERBOSE_MODE` is enabled;
the setup classifier never publishes that sentinel.

WP1.1a preserves the historical orientation rule: a negative center/directed-
normal dot product stages the second and third seed corners in reversed order.
For a single adjacent-face-count candidate at corner 1 or 2, a nonnegative
predicate leaves `Face::adjacentVertices` in its original order even though the
ring seeds rotate; a negative predicate publishes the rotated/swapped seed
order. BASE-locked cases cover candidates 0, 1, and 2 under both outcomes. A
complete reversed synthetic face publishes that historical orientation only
after its entire ring passes; the same reversed face with a missing source
rejects with both face vectors unchanged. This package changes no signed-volume
expression or orientation-dependent volume behavior (S7).

## D5 evidence and compatibility limit

Let `q_i` be the adjacent-vertex valence observed at face corner `i`. The
legacy 11-control branch predicate is exactly

```text
q_0 = 5 AND q_1 = 5 AND q_2 = 5.
```

An intended `5/6/6` face has a permutation of `(q_0,q_1,q_2) = (5,6,6)`.
It necessarily makes two conjuncts false, so it cannot execute the legacy
11-control branch. Supporting `5/6/6` is therefore a NET-NEW WP1.1b candidate,
not retained compatibility.

The checked-in closed icosahedron is deliberately unchanged pending D5. Each
face reports three adjacent-face-count candidates, preserves the historical
corner-zero priority, assembles 11 entries with nine distinct source IDs, and
reports two repeated source IDs. WP1.1a neither rejects, deduplicates, reorders,
nor repairs those aliases.

## Adversarial and mutation evidence

The `LegacyOneRingSafety` focused suite binds every rejection to a distinct
reason and compares serialized sizes and integer bytes for both face vectors
before and after the rejected call. Positive locks cover the pure regular
classifier, all six single-candidate/orientation combinations, and the accepted
icosahedron aliases.

An executable source-mutation campaign was run on 2026-08-27. Each manifest
entry copied the final worktree to a new temporary directory without `.git`,
performed exactly the textual transformation shown below in
`src/mesh/Mesh_setup_geometry.cpp`, deleted only the copied
`obj/test/Mesh_setup_geometry.o` and `bin/test_main`, rebuilt incrementally, and
ran the named focused test. The command pattern was:

```text
env -u OPENSUBDIV_ROOT make test -j4 [sanitizer flags when marked]
./bin/test_main --gtest_filter=<target>
```

The sanitizer flags were exactly:

```text
CFLAGS='-std=c++17 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer'
CXXFLAGS='-std=c++17 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer'
LDFLAGS='-fsanitize=address,undefined'
```

All mutant builds exited 0. Every targeted run exited nonzero, so the campaign
killed 13 of 13 mutants. Temporary copies were removed after their individual
runs; the driver and JSON result were kept outside the repository under
`/private/tmp` for coordinator evidence only and are not package artifacts.

| ID | Exact transformation | Target test | Mode | Result |
| --- | --- | --- | --- | --- |
| G01 | `if (face.adjacentVertices.size() != 3u)` -> `if (false && face.adjacentVertices.size() != 3u)` | `LaterFaceRejectionLeavesEarlierReadyFaceByteIdentical` | ASan+UBSan | test exit 1; accidental acceptance assertion fired |
| G02 | `if (!valid_vertex_index(vertex))` -> `if (false && !valid_vertex_index(vertex))` | `InvalidCornerAndAdjacentVertexIndicesHaveDistinctRejectionCodes` | ASan+UBSan | test exit -6; AddressSanitizer abort |
| G03 | `if (!regular && !allValenceFive)` -> `if (false && !regular && !allValenceFive)` | `FiveSixSixPredicateIsUnsupportedAndNeverExecutesLegacyMatrixSetup` | default | test exit 1; reason/throw assertions fired |
| G04 | `if (result.extraordinaryCornerCandidates.empty())` -> `if (false && result.extraordinaryCornerCandidates.empty())` | `NoAdjacentFaceCountMatchRejectsBeforeMutation` | default | test exit 1; reason/assignment assertions fired |
| G05 | `if (result.extraordinaryCornerCandidates.size() == 2u)` -> `if (false && result.extraordinaryCornerCandidates.size() == 2u)` | `AmbiguousAdjacentFaceCountMatchRejectsBeforeMutation` | default | test exit 1; accidental acceptance assertion fired |
| G06 | `if (!valid_vertex_index(candidate1))` -> `if (false && !valid_vertex_index(candidate1))` | `InvalidCornerAndAdjacentVertexIndicesHaveDistinctRejectionCodes` | default | test exit 1; invalid source was accepted and assertions fired |
| G07 | `return {OppositeNodeSearchState::Missing, -1};` -> `return {OppositeNodeSearchState::Unique, -1};` | `IncompleteOneRingRejectsBeforeMutationAndNeverStoresMinusOne` | default | test exit 1; reason assertions fired |
| G08 | `return {OppositeNodeSearchState::Ambiguous, -1};` -> `return {OppositeNodeSearchState::Unique, candidates.front()};` | `AmbiguousOppositeNodeRejectsBeforeMutation` | default | test exit 1; reason assertions fired |
| G09 | aggregate failure-block `return result;` -> removed | `IncompleteOneRingRejectsBeforeMutationAndNeverStoresMinusOne` | default | test exit 1; published `-1` assertion fired |
| G10 | `if (is_legacy_one_ring_rejection(classification.reasonCode))` -> `if (false && is_legacy_one_ring_rejection(classification.reasonCode))` | `LaterFaceRejectionLeavesEarlierReadyFaceByteIdentical` | default | test exit 1; accidental acceptance/byte assertions fired |
| G11 | ready-reason publication filter -> `if (false)` | `FiveSixSixPredicateIsUnsupportedAndNeverExecutesLegacyMatrixSetup` | default | test exit 1; unchanged-byte assertion fired |
| G12 | remove `orientedFaceVertices.clear()` on incomplete assembly | `ReversedFaceDoesNotPublishStagedOrientationWhenRingIsIncomplete` | default | test exit 1; empty-staged-orientation assertion fired |
| G13 | missing-node `if (param.VERBOSE_MODE)` -> `if (true)` | `MissingOppositeNodeDiagnosticHonorsVerboseMode` | default | test exit 1; quiet-output assertion fired |

The file-local opposite-search input-index check is deliberate
defense-in-depth, not a separately claimed semantic guard: all its call inputs
come from already validated face corners or previously validated opposite
sources, and the assignment chain short-circuits after a failure. Sentinel
initialization, duplicate reporting, and the preserved orientation predicate
are state/diagnostic invariants rather than additional guard-manifest entries.

The authoritative verification also compares serialized accepted outputs
produced by BASE `6acac80f09bcfdc27dd3b3eca1f55be02379147a` and the WP1.1a worktree. Those
bytes include regular face orientation and one-ring order, the accepted
icosahedron outputs, and the six single-candidate cases (candidate corners
0/1/2 under nonnegative and negative orientation outcomes).

The scoped claim is: unreachable index reads are now impossible and failures
are explicit. No broader geometry or scientific claim is made.
