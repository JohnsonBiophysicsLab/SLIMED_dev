# Option B Valence-5 Scientific Re-baselining Assessment

## Scope

This proof-only assessment checks the evidence required before Option B could
adopt stock OpenSubdiv extraordinary semantics on the approved closed
valence-5 icosahedron. The user authorized checking Option B, not selecting it.
The report therefore requires:

- `assessment_authorized:true`;
- `assessment_scope:"observational_scientific_rebaseline_planning_only"`;
- `option_b_selected:false`;
- `option_b_recommended:false`;
- `stock_semantics_scientifically_approved:false`;
- `physical_rebaselining_plan_proposed:true`;
- `physical_rebaselining_plan_authorized:false`;
- `implementation_work_authorized:false`;
- `production_route_enabled:false`;
- `valence5_opensubdiv_route_enabled:false`; and
- `current_slimed_valence5_fallback_preserved:true`.

It does not change dependencies, production formulas, scatter, OpenMP
reductions, checkpoint/output behavior, propagation, or broader-valence
routing.

## Known Scientific Change

The assessment reruns and binds the existing stock OpenSubdiv evidence rather
than treating a topology/source-order proof as scientific equivalence.
At the reviewed fixed tolerance `5e-6`:

- composed-row parity fails with maximum residual
  `0.7357563654581705`;
- `fBend` differs by as much as `7.108303140663388`;
- `fArea` differs by as much as `0.46106761515265404`;
- `fVolume` differs by as much as `0.062309089012307695`; and
- the extraordinary smooth-vertex masks differ, while causal sufficiency of
  that mask difference remains unproven.

The current dependency-free SLIMED serial/OpenMP baseline remains green on
global/per-face energy, vertex forces, normals, mean curvature, area, and
legacy volume. That current baseline is not evidence that stock OpenSubdiv
semantics preserve those channels.

## Proposed Re-baselining Plan

The assessment records five ordered channels:

1. Force is `characterized_non_parity`; scientific review must explicitly
   accept or reject the measured change.
2. Stock-versus-current global and per-face energy remains pending.
3. Stock-versus-current normals, mean curvature, area, and legacy volume
   remain pending.
4. Output-visible force and face-observable records remain pending.
5. Stock-semantics serial/OpenMP accumulation and repeatability remain
   pending.

This is a proposed plan, not an authorized plan. The next bounded evidence
lane is proof-only stock OpenSubdiv valence-5 energy and geometry observable
re-baselining. It must not install a route.

## Boundary

The report emits `decision_ready:false` and keeps Option B unselected. Its
exact remaining boundary is:

`review and explicitly authorize the proposed stock OpenSubdiv valence-5 physical re-baselining plan; Option B remains unselected`.

Run the opt-in assessment with:

```console
OPENSUBDIV_ROOT=/path/to/opensubdiv \
OPENSUBDIV_CXXFLAGS='-arch arm64' \
  ./scripts/run_irregular_valence5_option_b_scientific_rebaseline_assessment.sh \
  --json --check --require-opensubdiv
```
