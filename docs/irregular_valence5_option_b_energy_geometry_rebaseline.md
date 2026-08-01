# Option B Valence-5 Energy and Geometry Re-baselining

## Scope

This opt-in proof characterizes stock OpenSubdiv energy and geometry
observables on the approved positive-depth closed valence-5 11-control
stand-in. It is observational evidence only. In particular:

- `option_b_selected:false`;
- `option_b_recommended:false`;
- `stock_semantics_scientifically_approved:false`;
- `implementation_work_authorized:false`;
- `production_route_enabled:false`;
- `output_visible_evidence_complete:false`; and
- `decision_ready:false`.

The wrapper requires `OPENSUBDIV_ROOT`. It does not alter production or public
headers, default builds, fixtures, force formulas, scatter, OpenMP reductions,
checkpoint/output, propagation, optimizer behavior, dependency policy, or
broader-valence routing.

## Bound Identity

The report binds the approved fixture digests, the exact perturbed 12-source
coordinates, 20 ordered outward faces and matching Ptex indices, all twenty
production `11`-slot one-rings and their duplicate slots, and the ordered
three-sample plan. The derivative contract remains `s=v,t=w,u=1-v-w`, with
all seven source-keyed rows and duplicated mixed rows.

Stock candidate observables are checked by an independent executable that
parses the emitted rows and coordinates and recomputes them in separate
`long double` algebra. The oracle does not call
`element_energy_force_regular` or share candidate aggregation helpers.
It also emits its own curvature, regularization, area-constraint,
volume-constraint, and total global energies. Those totals are compared
directly with the candidate executable's independently emitted totals rather
than being reconstructed through shared Python aggregation. Candidate/oracle
agreement is required at `1e-10`; the authoritative
stock-versus-current policy remains the fixed reviewed relative tolerance
`5e-6`. There is no CLI tolerance capable of clearing a blocker.

The authoritative stock evidence binds reviewed expected values for all 10
global-energy components, all 200 ordered per-face energy components, and all
120 ordered per-face geometry components. Candidate and oracle vectors are
checked component-by-component with the fixed absolute tolerance `1e-12`, and
any failure reports scope, face where applicable, channel, expected, actual,
delta, and tolerance. This policy cannot be changed from the CLI.

A stable nine-decimal scientific-notation SHA-256 digest remains reporting-only:
`982d0be8559491842125cf5b56d35d06c4e90441c7f8e85214585a140f76622d`.
It does not authorize readiness. In particular, a real candidate/oracle
co-mutation of global curvature by `1e-7` retains that rounded digest but fails
the authoritative vector gate, while a sub-`1e-12` sanity mutation passes.
Candidate-only global aggregation corruption and candidate/oracle co-mutation
of non-maximum energy and geometry components are also binding failures. Both
numeric package readers require whitespace followed by true EOF and reject
trailing nonnumeric tokens.

## Energy Semantics

Per-face production energy contains curvature and regularization only. Area
and volume constraint energies are global additions, so the proof does not
invent per-face area or volume energy. Global energy is independently
aggregated from all canonical per-face values and stock area/legacy-volume
totals.

The measured stock/current maxima are:

- global energy: curvature delta `83.84946348746075`;
- per-face energy: face `11` curvature delta `4.386320459494776`; and
- per-face geometry: face `11` mean-curvature delta
  `2.5747867579624395`.

The proof emits every current, stock, and absolute-delta component in
canonical order, plus maximum locations containing face where applicable,
channel, current value, stock value, and delta. Geometry preserves normalized
weighted normals, current mean-curvature accumulation, area, and legacy
first-component volume.

These results characterize changed stock semantics. They do not attribute the
change solely to the extraordinary mask and do not scientifically approve it.

## Remaining Boundary

No output writer is executed or parsed, therefore
`output_visible_evidence_complete:false` and output evidence remains pending.
Stock serial/OpenMP evidence also remains pending. The exact boundary is:

`scientific review of measured stock energy and geometry changes; Option B remains unselected and output evidence remains pending`.

Run the proof with:

```console
OPENSUBDIV_ROOT=/path/to/opensubdiv \
OPENSUBDIV_CXXFLAGS='-arch arm64' \
  ./scripts/run_irregular_valence5_option_b_energy_geometry_rebaseline.sh \
  --json --check --require-opensubdiv
```
