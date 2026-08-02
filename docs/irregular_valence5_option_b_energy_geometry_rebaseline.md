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
checked component-by-component with a fixed scope-aware cross-platform
absolute envelope:

- global energy: `3e-5`;
- per-face energy: `2e-6`; and
- per-face geometry: `3e-7`.

Any failure reports scope, face where applicable, channel, expected, actual,
delta, and that scope's tolerance. The envelope is independent from the
stricter `1e-10` candidate/oracle consistency check and the reviewed `5e-6`
stock-versus-current relative policy. None of these policies can be changed
from the CLI.

A stable nine-decimal scientific-notation SHA-256 digest remains reporting-only:
`982d0be8559491842125cf5b56d35d06c4e90441c7f8e85214585a140f76622d`.
It does not authorize readiness and may differ across supported floating-point
environments. The reviewed 330-component vector remains the center of the
authoritative envelope, and candidate/oracle agreement must still pass
independently. Binding tests accept in-envelope perturbations and reject a
candidate/oracle co-mutation beyond any scope's envelope. Candidate-only global
aggregation corruption and large candidate/oracle co-mutations of non-maximum
energy and geometry components are also binding failures. Both numeric package
readers require whitespace followed by true EOF and reject trailing nonnumeric
tokens.

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

## WSL Verification Follow-up (2026-08-01)

The branch was resumed on Ubuntu 26.04 under WSL with GCC 15.2.0 and an
upstream OpenSubdiv `v3_7_0` install built from commit
`9dab8a47bfbb1388ec8388fe61f5f916e6123f38`.

One portability false green from the earlier environment was closed without
changing scientific semantics or tolerance policy:

- the independent oracle's local `finite` predicate collided with the C math
  overload set under GCC 15, so the predicate is now named `finite_value` and
  its dependency-free inventory test compiles the oracle whenever a C++17
  compiler is available.

The default PR-ready gate builds all five C++ targets, but its 145-test binary
has one pre-existing failure under GCC 15:
`SharedHelperRecordsScaffoldEnergyAndForceSideEffects` constructs an expected
three-component force with two uninitialized components. The observed garbage
values are approximately `4.94e-310`; the evaluated production components are
zero. That test is outside this evidence lane's protected path set, so it
remains unchanged and is recorded as a separate baseline-test blocker rather
than broadening this PR.

The WSL OpenSubdiv proof reached the canonical gate. Candidate and independent
long-double oracle agree with maximum absolute difference
`4.547473508864641e-13`, while both show bounded floating-point drift from the
reviewed canonical vector.
The WSL candidate global energy is
`[1195.2873835811804, 3.612215391293492, 0.0480708942360472, 0, 0, 0, 0, 0, 0, 1198.94766986671]`;
the largest canonical delta is total energy
`2.6336025939599494e-05`, and its reporting digest is
`21271fd65e4d98d5db38b1a31309738a4b885c0e3088dc8d3ff3874334b73ef3`.

The measured WSL maxima by scope are `2.6336025939599494e-05` for global
energy, `1.7738014790324996e-06` for per-face energy, and
`2.4650185731500684e-07` for per-face geometry. The lightweight
cross-platform policy therefore retains the reviewed vector as its center and
uses fixed bounds of `3e-5`, `2e-6`, and `3e-7`, respectively. It does not add
a WSL-specific vector or weaken candidate/oracle consistency or scientific
stock/current parity. The exact dependency-present WSL proof passes this
contract. The digest remains reporting-only. Output-visible evidence remains
incomplete. The follow-on stock serial/OpenMP accumulation and fixed-thread
repeatability evidence is complete under its separate proof-only lane.

## Output Follow-up Boundary

The follow-on output writer characterization now executes and parses the real
global-energy, per-face-energy, and restart-checkpoint writers. It confirms
that total vertex force and record energy round-trip exactly, but the current
formats omit force families and face geometry, use insufficient default CSV
precision, and expose a malformed per-face energy schema. Consequently,
output-visible evidence remains incomplete and
`output_visible_evidence_complete:false` remains binding even though the
output characterization is complete. Output-contract repair is not authorized.
The exact boundary is:

`review and explicitly authorize an output-contract repair lane; Option B remains unselected`.

Run the proof with:

```console
OPENSUBDIV_ROOT=/path/to/opensubdiv \
OPENSUBDIV_CXXFLAGS='-arch arm64' \
  ./scripts/run_irregular_valence5_option_b_energy_geometry_rebaseline.sh \
  --json --check --require-opensubdiv
```
