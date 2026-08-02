# Option B scientific selection record and implementation plan

## Recorded decision

On 2026-08-02, after the evidence packet merged in PR #162, the user explicitly instructed: **“Accept Option B.”** This records acceptance of stock OpenSubdiv extraordinary-valence semantics as the new positive-depth valence-5 physical baseline, including the measured force, energy, and geometry changes bound by the predecessor packet.

The machine-readable record reports:

- `decision:"accept"`
- `decision_recorded:true`
- `option_b_selected:true`
- `option_b_recommended:false`
- `stock_semantics_scientifically_approved:true`
- `scientific_rebaseline_plan_authorized:true`
- `production_routing_plan_authorized:true`
- `implementation_authorized:false`
- `production_route_enabled:false`
- `current_slimed_valence5_fallback_preserved:true`

Selection and scientific approval do not themselves change runtime behavior. The current SLIMED positive-depth valence-5 fallback remains active until a separate implementation and activation change passes the standing PR reviewer and user-approval gates.
Implementation and production routing remain disabled.

## Accepted scientific baseline

Acceptance covers the complete measured evidence, including the composed-row maximum difference `0.7357563654581705`, bending-force difference `7.108303140663388`, global curvature-energy difference `83.84946348746075`, per-face curvature-energy difference `4.386320459494776`, and face mean-curvature difference `2.5747867579624395`. It also accepts that stock and current semantics are not equivalent and that sole-mask causal sufficiency was not proven.

The accepted stock implementation remains bound to the completed operational evidence: serial/OpenMP accumulation differed by at most `2.2737367544323206e-13` under the `1e-10` policy, and all repaired output round trips were exact.

## Authorized plan, not implementation

This record authorizes the following plan. It does not authorize source-level implementation or routing activation.

### Phase 1 — guarded stock valence-5 row provider

Create an OpenSubdiv-enabled, default-off provider parallel to the existing valence-4 seam. It must:

- remain compiled only when `OPENSUBDIV_ROOT` is supplied;
- accept only the reviewed closed positive-depth valence-5 topology and reject unsupported identity, ordering, cardinality, or sample plans before mutation;
- preserve original SLIMED source identifiers and the reviewed seven-row derivative convention;
- emit stock whole-Ptex rows rather than claiming parity with the existing `11 = 4 + 3 + 4` composition;
- expose structured execution and rejection diagnostics;
- add no production caller and perform no production mutation in this phase.

The first implementation PR should be limited to the provider, a deterministic harness, default-build stubs, compile/link coverage, and source/row identity tests. It must reuse the merged experimental evidence rather than copy an unreviewed evaluator path into production.

### Phase 2 — guarded face-loop integration and scientific re-baseline

After Phase 1 is independently approved, add a runtime-opt-in face-loop transaction that evaluates the provider’s stock rows through the existing energy/force algebra. The transaction must reject atomically before mesh mutation, retain the current fallback when the build dependency or runtime gate is absent, and cover force, global/per-face energy, geometry, output, restart, serial/OpenMP, and repeatability behavior.

Re-baselining must replace affected valence-5 expectations with the accepted values and fixed reviewed envelopes. It must not make stock/current parity true, hide residuals, or broadly relax unrelated tolerances.

### Phase 3 — explicit activation

Default production activation is a separate decision after guarded execution passes. The activation PR must demonstrate dependency-present and dependency-absent behavior, preserve a documented rollback to the current fallback, pass all default and OpenSubdiv-enabled suites, and receive both dedicated reviewer PASS and explicit user approval.

## Rollback and compatibility boundaries

- Default builds remain OpenSubdiv-free.
- Unsupported or unreviewed irregular topologies remain rejected or use their current reviewed behavior.
- Regular and valence-4 OpenSubdiv routes retain their existing gates and semantics.
- Checkpoint V1/V2 compatibility and all ten CSV energy channels remain unchanged.
- The fallback cannot be removed in the provider or integration phases.

## Reproduce

From a WSL/Linux checkout:

```bash
scripts/run_irregular_valence5_option_b_selection_record.sh --check --json
```
