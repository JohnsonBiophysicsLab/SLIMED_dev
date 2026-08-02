# Option B Valence-5 Output Contract

## Scope

PR #157 characterized the production output writers against the approved
closed valence-5 fixture under stock OpenSubdiv Option B semantics. It found
three concrete contract gaps: incomplete and low-precision global energy CSV
rows, a malformed and incomplete face-energy CSV schema, and restart files
that retained totals but omitted force families and face observables.

This follow-on lane is the explicitly authorized output-contract repair. It is
limited to the existing writers and loader, their tests, and this proof. It
does not change evaluators, force formulas, scatter or OpenMP reduction order,
optimizer behavior, fixtures, dependencies, or production routing. Option B
remains unselected, unrecommended, scientifically unapproved, and unrouted.

## Repaired CSV Contracts

`EnergyForce.csv` now writes all ten `Energy` channels followed by mean force:

`E_Curvature,E_Area,E_Volume,E_Thickness,E_Tilt,E_Regularization,E_HarmonicBond,E_GagScaffolding,E_IdealizedProteinLattice,E_Total ((pN.nm)),Mean Force (pN)`

`ElementFaceEnergy.csv` now writes face index followed by those same ten energy
channels. Its header and every data row are both eleven columns wide. Both
writers use 17 significant digits, and the proof requires exact numeric
round-trip against the staged stock evidence; there is no tolerance override.
The three checked-in pandas plotting scripts now read the CSV header and rename
the five legacy plotting columns by name, so the additional channels do not
break those consumers.

## Restart Contract

New checkpoints use `SLIMED_RESTART_V2`. In addition to the V1 optimization,
coordinate, scaffold, and record state, V2 serializes:

- all eight current `Force` matrices for every vertex;
- all eight previous-force matrices and all eight NCG-direction matrices;
- each face normal, mean curvature, area, legacy volume, and all ten face
  energy channels.

The loader accepts both V1 and V2. A V1 file continues to restore its historical
total-force-only state, while a V2 file restores every newly serialized field.
The loader rejects trailing tokens after `END`. Unit tests construct a V1 file
from V2 output to bind backward compatibility rather than merely accepting the
version marker.

## Verification Boundary

The proof stages the independently checked Option B stock energy, geometry,
and force evidence in a real `Model`, executes all three production writers,
loads the V2 checkpoint, and parses both CSVs. It requires:

- all CSV values to match exactly at double round-trip precision;
- all current force families, previous force families, and NCG direction
  families to round-trip exactly;
- face normals, mean curvature, area, legacy volume, and energy to round-trip
  exactly; and
- independent aggregation of all 2,160 per-face force components into the 108
  source-force components before accepting the output claim.

The checkpoint harness assigns distinct finite nonzero sentinels to every
component in all 24 force groups (eight current, eight previous, and eight NCG)
after recording the stock mean-force observable. It compares each group
independently and makes harness success depend on all 24 exact-zero maxima, so
an omitted zero-valued family cannot produce a false green.

The output-visible evidence gap identified by PR #157 is closed. The stock
serial/OpenMP evidence is also complete under its separate proof-only lane.
The remaining boundary is scientific review and explicit Option B selection;
production valence-5 routing remains disabled.

## Implementation Record

This repair was implemented on 2026-08-02 from PR #160's merge commit
`73bfbf1e90626eaf829d85c2a77916aaf816076f`. The work sequence was: inventory
all affected writers/readers, define the narrow schema and V1/V2 compatibility
boundary, implement and unit-test the production I/O, bind the real-writer
OpenSubdiv proof, then update the readiness inventories and documentation.

WSL verification completed for all five default build targets (`serial`,
`omp`, `dyna`, `dyna_omp`, and `test`). The five focused output/restart tests
pass, all 18 output/readiness Python tests pass with OpenSubdiv 3.7.0 present,
and the real-writer proof reports exact zero serialization and checkpoint
differences. The complete C++ suite remains at the documented GCC 15 baseline
of 147/148: `SharedHelperRecordsScaffoldEnergyAndForceSideEffects` still fails
because its expected three-component force has two uninitialized components.
That pre-existing test defect is outside this repair and is not caused by the
output changes.

Run the proof with:

```console
OPENSUBDIV_ROOT=/path/to/opensubdiv \
  ./scripts/run_irregular_valence5_option_b_output_visibility.sh \
  --json --check --require-opensubdiv
```
