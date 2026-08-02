# Option B scientific decision packet

## Result

The Option B evidence program is complete and ready for an explicit scientific decision. This packet does not select or recommend Option B, grant scientific approval, authorize implementation, or enable production routing. Until an explicit decision is recorded, the current dependency-free SLIMED valence-5 fallback remains the safe default.

The machine-readable gate reports:

- `evidence_complete:true`
- `decision_ready_for_user:true`
- `decision_recorded:false`
- `option_b_selected:false`
- `scientific_approval_granted:false`
- `implementation_authorized:false`
- `production_route_enabled:false`
- `current_slimed_valence5_fallback_preserved:true`

## Evidence completed

| Lane | Pull request | Merge commit | Finding |
| --- | ---: | --- | --- |
| Scientific re-baseline plan | #152 | `24cbc8c79259e4ee6dec039b87d816c03ea75560` | Defined the observational lanes without selecting Option B. |
| Energy and geometry | #153 | `5d8ef458f738343df82050e4f02b9647064fd75f` | Bound all 330 observables and independently reproduced the stock candidate. |
| Output characterization | #157 | `c6569c6fdbcc2de72c10951e7c42699fe9d4a6e6` | Exercised the real output path and exposed contract gaps. |
| Serial/OpenMP | #160 | `73bfbf1e90626eaf829d85c2a77916aaf816076f` | Verified stock accumulation across 1, 2, and 4 threads with five repeats. |
| Output contract repair | #161 | `93b18c683a19e3c35b595e8c85ae111b04caa967` | Preserved all 24 checkpoint force groups and five face fields exactly; both CSV schemas carry all ten energy channels. |

The packet binds the merged runner contents by SHA-256 so later evidence changes cannot silently inherit this decision-ready state.

## Scientific change that must be accepted or rejected

Stock OpenSubdiv and the current SLIMED fallback are not equivalent at positive-depth valence 5. The largest measured differences include:

- composed subdivision row: `0.7357563654581705`
- bending force: `7.108303140663388`
- area force: `0.46106761515265404`
- volume force: `0.062309089012307695`
- global curvature energy: `83.84946348746075`
- per-face curvature energy: `4.386320459494776`
- face mean curvature: `2.5747867579624395`

The extraordinary-vertex masks differ, but mask-policy causal sufficiency has not been proven. Therefore the engineering results establish reproducibility and operational compatibility, not physical correctness.

The stock implementation is internally stable: its maximum serial/OpenMP difference was `2.2737367544323206e-13` against a `1e-10` tolerance, and the repaired output round trips were exact. Those facts do not establish scientific acceptance of the changed values.

## Explicit decision required

The required decision is: explicitly accept, reject, or defer Option B stock OpenSubdiv extraordinary-valence semantics after scientific review of the listed force, energy, and geometry changes.

- **Accept:** accept the measured changes as the new physical baseline. This authorizes drafting a separate production-routing and re-baselining plan; it does not activate routing in this packet.
- **Reject:** retain the current SLIMED valence-5 fallback and close Option B.
- **Defer:** retain the current fallback and name the additional physical validation or acceptance thresholds needed.

If Option B is accepted, the next implementation must be a separate reviewed pull request, rebaseline affected valence-5 scientific expectations, preserve a documented rollback path, and repeat the existing compatibility suites before routing can be enabled.

## Reproduce

From a WSL/Linux checkout:

```bash
scripts/run_irregular_valence5_option_b_scientific_decision.sh --check --json
```
