# Option B Phase 1 stock valence-5 row provider

## Scope

This change implements only Phase 1 of the accepted Option B plan. It adds a
guarded, default-off OpenSubdiv row provider for the reviewed closed
positive-depth valence-5 fixture. It does not add a production face-loop
caller, execute energy or force algebra, mutate a mesh, re-baseline scientific
expectations, or enable production routing. Phase 2 remains separately gated.

The provider is compiled only with `USE_OPENSUBDIV_VALENCE5=1` and an explicit
`OPENSUBDIV_ROOT`. This flag is separate from `USE_OPENSUBDIV_REGULAR`, so the
Phase 1 seam cannot implicitly activate the existing regular route. A default
build exposes the same API and returns an explicit dependency-disabled
rejection.

## Bound contract

The enabled provider accepts only the exact reviewed fixture:

- 12 original source vertices, each with valence 5;
- 20 oriented physical triangular faces in fixture order;
- one Ptex face per fixture face;
- the fixed three-point plan `(1/6,1/6)`, `(1/6,4/6)`, `(4/6,1/6)`;
- seven SLIMED derivative rows per sample, with the mixed row duplicated;
- exactly nine sorted original SLIMED source IDs per physical face.

Rows are generated in double precision from stock whole-Ptex OpenSubdiv limit
stencils. The provider stages the complete `20 x 3 x 7 x 9` source-keyed
package and returns it only after topology, source mapping, sample identity,
finite-value, constant-field, and mixed-row checks pass. Unsupported topology
or a missing build dependency is rejected without partial publication.

## Verification result

The independent runner builds both the default stub and enabled provider into
WSL-native temporary directories. It executes the enabled harness twice and
compares the dense-expanded rows against the accepted float source-order proof.
The reviewed result is:

- exact tensor shape: `20x3x7x9_source_keyed`;
- maximum absolute difference: `6.568566814357801e-7`;
- comparison tolerance: `5e-6`;
- byte-identical repeated execution: true;
- invalid oriented topology rejected: true;
- production one-rings unchanged: true;
- production route, face loop, force path, and mesh mutation: all false.

## Reproduce in WSL

```bash
OPENSUBDIV_ROOT=/opt/opensubdiv-3.7.0 \
  scripts/run_irregular_valence5_opensubdiv_row_provider.sh \
  --json --check --require-opensubdiv

python3 scripts/inventory_irregular_valence5_opensubdiv_row_provider.py \
  --json --check
```

The next boundary is a separately reviewed and explicitly approved Phase 2 PR
for guarded face-loop integration and scientific re-baselining. This provider
does not authorize that work.
