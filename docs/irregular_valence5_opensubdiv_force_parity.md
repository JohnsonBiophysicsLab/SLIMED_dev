# Valence-5 OpenSubdiv Force-Parity Diagnostic

This opt-in proof follows the per-face source-order and weighted-transpose
contract established by PR #144. It compares actual force rows on the approved
closed valence-5 icosahedron without enabling a route.

Run it with:

```console
OPENSUBDIV_ROOT=/path/to/opensubdiv \
OPENSUBDIV_CXXFLAGS='-arch arm64' \
  scripts/run_irregular_valence5_opensubdiv_force_parity.sh \
  --json --require-opensubdiv
```

Without `OPENSUBDIV_ROOT`, the wrapper emits a successful machine-readable
skip. With the dependency present, it builds two standalone reporters:

- the production reporter executes
  `Mesh::element_energy_force_irregular_11()` at positive depth and exports
  per-face source-keyed `fBend`, `fArea`, and `fVolume`;
- the OpenSubdiv probe exports a fresh `20 x 3 x 7 x 12` row tensor; and
- a separate C++ harness evaluates those rows with the existing
  `Mesh::element_energy_force_regular()` scientific algebra.

The comparison is per face, original source ID, force family, and spatial
component. It therefore cannot pass through cancellation in an aggregate mesh
force. The production reporter and OpenSubdiv harness each evaluate their own
rows and back-projection before the Python comparator sees either result.

## Result

The diagnostic runs successfully, but force parity does not pass. Against the
reviewed relative tolerance `5e-6` and production force scale
`25.07039362582162`, the scaled absolute tolerance is
`0.0001253519681291081`. The measured maximum absolute differences are:

- `fBend`: `7.108303140663388`;
- `fArea`: `0.46106761515265404`; and
- `fVolume`: `0.062309089012307695`.

The exact blocker is that direct whole-Ptex OpenSubdiv rows at the frozen
three-sample plan do not reproduce the existing positive-depth
`11 = 4+3+4` force composition. This is not a precision or tolerance-policy
issue.

The report emits `proof_only:true`, `not_production_routing:true`,
`production_route_enabled:false`, and `production_scatter_executed:false`.
It records both
`positive_depth_production_force_path_executed:true` and
`opensubdiv_rows_evaluated_by_existing_force_algebra:true`, but it does not
install OpenSubdiv rows in production or execute production scatter.

The next reviewed step is a proof-only integration-domain/composition
diagnostic. It must determine whether OpenSubdiv rows need the same
positive-depth child-domain decomposition and quadrature mapping as the
current `4+3+4` route. Production valence-5 routing remains disabled.
