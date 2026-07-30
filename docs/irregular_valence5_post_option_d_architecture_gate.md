# Post-Option-D Valence-5 Architecture Gate

## Scope

This proof-only decision gate consumes merged PR #149 at commit
`54fecddb60edd05c0ec4677c87f684ebe5b50301` and merged PR #150 at commit
`636a6583fea3e76e42e8b6b48699e40bc80f4e4d` as binding predecessors. It
records the remaining user decision boundary after the authorized
alternate-library survey completed. It does not select or authorize an
architecture, scientific semantics, dependency change, implementation, or
production route.

The deterministic report requires:

- `decision_selected:false`;
- `selected_option:null`;
- `recommended_option:null`;
- `preferred_option:null`;
- `automatically_next_option:null`;
- `proceed_interpreted_as_option_selection:false`;
- `scientific_approval_granted:false`;
- `physical_rebaselining_plan_authorized:false`;
- `dependency_license_maintenance_approval_granted:false`;
- `dependency_policy_changed:false`;
- `patch_or_vendoring_performed:false`;
- `implementation_work_authorized:false`;
- `production_route_enabled:false`;
- `valence5_opensubdiv_route_enabled:false`;
- `current_slimed_valence5_fallback_preserved:true`; and
- `option_d_reopened:false`.

No option is selected, recommended, preferred, or automatically next.
Authorization to create this gate does not select Option B or C.

## Binding Predecessors

The PR #149 canonical option records are bound by SHA-256
`a23f7974b66ee17a0ffbfffe5a102beeed1965393365d5de36ad0228b1ff1b4c`.
Their order remains exactly A, B, C, D and every historical PR #149 status
remains `unselected`.

The report binds the complete canonical PR #150 report by SHA-256
`c773ac3cbc25438325aa5f3b7037b49541a06e7038dd556fa47a320e1b52328f`.
It also exposes and independently checks the predecessor facts:

- `retrieval_date:"2026-07-30"`;
- the SLIMED valence-5 mask is exactly
  `neighbor_weight:0.075`, `center_weight:0.625`;
- the required capability order is frozen from triangular Loop support
  through source/order/cardinality and chain-rule compatibility;
- the ordered candidate IDs are exactly `cgal`, `libigl`, `openmesh`, and
  `pmp-library`;
- the pinned candidates are CGAL 6.2, libigl 2.6.0, OpenMesh 11.0, and
  pmp-library 3.0.0;
- every candidate is non-viable, unselected, and unrecommended;
- `viable_candidate_ids:[]`;
- Option D was authorized only with
  `authorization_scope:"observational_feasibility_only"`;
- that authorization was not architecture selection;
- installability, compile, and link probes were not executed; and
- the current SLIMED positive-depth valence-5 fallback remains preserved.

The exact predecessor result remains:

`no viable candidate in the reviewed finite non-exhaustive set provides exact extraordinary Loop limit-surface evaluation with first and second parametric derivatives and a public evaluator-bound custom-mask seam that preserves the SLIMED valence-5 source and chain-rule contract`.

Candidate-set drift, a fabricated viable candidate, installability overclaim,
or any changed predecessor result, blocker, or authorization state fails the
gate.

## Options

### A: Current Behavior

Preserve the current dependency-free SLIMED positive-depth valence-5
fallback/status quo. No implementation work is required. This current
behavior is not an architecture selection.

### B: Stock OpenSubdiv Semantics

This option remains unselected. Before implementation, the user must
explicitly select Option B, explicitly approve the changed scientific
semantics, and approve a separate physical re-baselining plan covering force,
energy, geometry, output, and serial/OpenMP behavior.

### C: Patch, Fork, or Vendor OpenSubdiv

This option remains unselected. Before implementation, the user must
explicitly select Option C and explicitly approve dependency, license, and
maintenance policy. Scientific validation follows that approval and must
complete before implementation.

### D: Alternate-Library Survey

The observational survey is completed with no viable candidate in the
reviewed finite non-exhaustive set. It may be reopened only by a separate
explicit authorization accompanied by materially new upstream or candidate
evidence. Both prerequisites are required. This gate does not reopen it. Its
machine result is
`no_viable_candidate_in_reviewed_finite_non_exhaustive_set`.

## Boundary

The only architecture-changing paths exposed by this gate are the precise
future user decisions for B or C above. Neither decision has been made.
Scientific approval, dependency approval, patching or vendoring,
implementation work, fallback removal, and route activation all remain false.
The exact remaining boundary is:

`preserve the current fallback/status quo; or separately approve scientific re-baselining for stock OpenSubdiv extraordinary semantics; or separately approve patch/fork/vendor dependency, license, and maintenance investigation; Option D may reopen only with materially new evidence and explicit authorization`.

Run the deterministic report with:

```console
./scripts/run_irregular_valence5_post_option_d_architecture_gate.sh --json --check
```

Run its source and scope inventory with:

```console
python3 scripts/inventory_irregular_valence5_post_option_d_architecture_gate.py --check
```
