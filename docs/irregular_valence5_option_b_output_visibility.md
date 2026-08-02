# Option B Valence-5 Output Visibility Characterization

## Scope

This is an observational output-visibility characterization for the approved
closed valence-5 fixture under stock OpenSubdiv Option B semantics. It consumes
the independently checked energy/geometry evidence and the existing force
characterization, stages those values in a proof-local `Model`, then executes
and parses all three real production writers relevant to the requested state:

- `write_energy_force_data_to_csv`;
- `write_element_face_energy_to_csv`; and
- `write_model_restart_checkpoint`, followed by the production checkpoint
  loader.

The lane does not change those writers, public headers, production formulas,
routing, dependencies, output formats, checkpoints, OpenMP reductions,
optimizer behavior, or fixtures. Option B remains unselected, unrecommended,
scientifically unapproved, unimplemented, and unrouted.

## Bound Inputs

The proof reuses the fixture, 20 ordered outward faces, perturbed coordinates,
OpenSubdiv rows, and fixed energy/geometry envelope from the prior re-baseline.
It independently executes the existing force algebra on the same rows and
aggregates the three force families to the twelve original source vertices.
The stock/current force and observable non-parity remains intentional evidence,
not a failure of this output characterization.

## Writer Results

`EnergyForce.csv` executes and parses with its existing eight-column schema.
It exposes seven of ten global energy fields plus mean force, omitting volume,
thickness, and tilt. The writer uses default stream precision, producing a
maximum stock serialization difference of `0.002616418819570754` in WSL.

`ElementFaceEnergy.csv` executes and parses, but its header declares five
columns while each data row contains four values. The face regularization term
is not written; total energy occupies the fourth value under the
`E_Regularization` header, and no fifth value exists for `E_Total`. Default
precision produces a maximum serialization difference of
`4.713969291714193e-05` against the value actually written.

The restart checkpoint preserves its record energy and total vertex force at
the existing 17-digit precision: both round-trip maxima are exactly zero. It
does not serialize the separate bending, area, and volume force families.
It also does not preserve face energy, normals, mean curvature, area, or legacy
volume. No other production output writer exposes those face observables.

## Decision Boundary

The writers have now been executed and parsed, so the characterization itself
is complete. Output-visible evidence remains incomplete because the existing
output contract cannot represent the full reviewed stock evidence and one CSV
schema is malformed. Output-contract repair is not authorized by this lane.

The exact next boundary is:

`review and explicitly authorize an output-contract repair lane; Option B remains unselected and stock serial/OpenMP evidence remains pending`.

Run the proof with:

```console
OPENSUBDIV_ROOT=/path/to/opensubdiv \
  ./scripts/run_irregular_valence5_option_b_output_visibility.sh \
  --json --check --require-opensubdiv
```
