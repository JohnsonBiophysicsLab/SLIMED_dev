# Option B Phase 2 guarded face-loop integration

## Scope

This change implements Phase 2 only for the accepted closed, positive-depth
valence-5 fixture. It connects the Phase 1 stock OpenSubdiv rows to the shared
production membrane face loop and completion phases, but it does not install a
default production route. `Mesh::Compute_Energy_And_Force()` does not inspect
the Phase 2 gate and retains the current fallback. Phase 3 remains separately
gated and requires its own reviewer PASS and explicit user approval.

The guarded caller requires both:

- an explicit `Valence5Phase2Request` whose reviewer-approved bit is true; and
- `SLIMED_USE_OPENSUBDIV_VALENCE5_PHASE2=1` at runtime.

It also requires an OpenSubdiv-enabled build. Dependency-disabled builds retain
the provider's structured rejection and perform no mutation.

## Transaction boundary

The caller validates the exact ordered N=2 three-sample quadrature plan, the
three one-third weights, the Phase 1 provider package, the nine-source mapping
for every face, finite coordinates and destinations, staged face/global
geometry, and a scientific dry run before entering the shared production
transaction. The production seam validates the complete destination and row
package again before its first write.

The actual transaction publishes stock face area and legacy volume, clears the
current force/energy state, executes the existing
`element_energy_force_regular` algebra through the production face loop,
reduces source-keyed force contributions in the existing thread-buffer shape,
and executes the unchanged regularization, total-force, total-energy, and
boundary completion phases. It never populates, clears, reorders, or consumes
the legacy production one-rings; the guarded mapping explicitly marks them as
bypassed while stock forces remain keyed to original source IDs.

Postconditions compare production face observables and the three membrane force
families to the pre-mutation scientific dry run under the reviewed `1e-10`
tolerance. A postcondition failure is a runtime error, not an input rejection;
all ordinary gate/input rejections occur before mutation.

The enabled harness also serializes the exact double-precision Phase 1 row
package, coordinates, parameters, and regularization terms into the existing
standalone long-double oracle. That oracle does not call the production
`element_energy_force_regular` implementation. Its independently recomputed
global energy, per-face energy, and geometry must agree with the Phase 2
production result within the existing `1e-10` oracle tolerance.

## Scientific and compatibility verification

The runner binds production output to the accepted 330-component stock Option B
baseline rather than current-SLIMED parity. Phase 1 deliberately replaced the
earlier float proof rows with the reviewed double-precision provider; Phase 2
therefore records new fixed global and per-face energy expectations from that
provider while retaining the accepted geometry expectation. The measured
double-provider shift from the predecessor float evidence is reported
separately and is not hidden as parity. It retains the fixed reviewed
cross-platform envelopes around the Phase 2 expectations:

- global energy: `3e-5`;
- per-face energy: `2e-6`;
- per-face geometry: `3e-7`;
- production dry-run and serial/OpenMP comparison: `1e-10`.

It additionally requires exact repeatability, parses the existing
`EnergyForce.csv` and `ElementFaceEnergy.csv` writers, and requires exact V2
checkpoint round trips for global energy, per-face energy, normals, mean
curvature, area, legacy volume, and the curvature/area/volume force families.
The ten-channel energy schemas and V1/V2 checkpoint formats are unchanged.

The reviewed WSL run with OpenSubdiv 3.7.0 passed with:

- exact fixed Phase 2 global and per-face energy expectations;
- geometry maximum difference `2.0762915764471757e-7` against the accepted
  `3e-7` envelope;
- serial/OpenMP membrane-force maximum difference
  `1.021405182655144e-14`;
- serial/OpenMP energy/geometry maximum difference
  `6.175615574477433e-16`;
- independent long-double replay maximum difference
  `3.552713678800501e-14` against the fixed `1e-10` tolerance;
- exact repeatability, CSV serialization, and restart round trips.

The separately reported Phase 1 double-provider shifts from the predecessor
float evidence are `0.0013724397249461617` globally and
`7.012976303144569e-5` per face. Those values explain the precision-specific
rebaseline; they are not presented as stock/current parity or absorbed by a
wider tolerance.

Default, valence-4, and regular OpenSubdiv routing are not selected or modified
by this API. Unsupported topology, identity, source cardinality, sample plan,
or destination state is rejected. The accepted stock/current residuals remain
scientifically real; this implementation makes no parity claim and relaxes no
unrelated tolerance.

## Reproduce in WSL/Linux

Dependency-disabled contract:

```bash
scripts/run_irregular_valence5_option_b_phase2_face_loop.sh --check --json
```

Full enabled suite:

```bash
OPENSUBDIV_ROOT=/opt/opensubdiv-3.7.0 \
  scripts/run_irregular_valence5_option_b_phase2_face_loop.sh \
  --check --json --require-opensubdiv
```

Phase 3 remains separately gated: this Phase 2 API reports
`production_route_enabled:false`, `default_evaluator_caller:false`, and
`phase3_activation_authorized:false` even after the real production face loop
executes successfully.
