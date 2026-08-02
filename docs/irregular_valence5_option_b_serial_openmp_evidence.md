# Option B Valence-5 Serial/OpenMP Evidence

## Scope

This proof-only lane closes the stock OpenSubdiv Option B accumulation and
fixed-thread repeatability item for the approved closed valence-5 fixture. It
reuses the independently validated stock energy, geometry, and force vectors;
it does not select or route Option B and does not modify production code.

The harness replays the production accumulation shape with real OpenMP:

- each face writes only its own indexed energy, geometry, and force records;
- curvature energy, regularization energy, area, and legacy volume use real
  OpenMP scalar reductions matching the production reduction class;
- each OpenMP thread accumulates 108 source-force components into private
  storage, then force buffers reduce in ascending thread-index order; and
- requested thread counts 1, 2, and 4 each execute five times with dynamic
  OpenMP teams disabled.

The scientific inputs remain deliberately non-parity evidence. The independent
long-double energy oracle and canonical observable envelope must pass, while
stock/current energy/geometry parity and force parity must remain false.
The proof independently recomputes all 108 aggregate force components from the
2,160 reviewed per-face components before accepting the harness output.

## Results

On Ubuntu 26.04 under WSL with OpenSubdiv 3.7.0, the maximum serial/OpenMP
accumulation difference is `2.2737367544323206e-13`, below the fixed `1e-10`
absolute policy. The measured channel maxima are:

- curvature, area, and volume force: `1.0658141036401503e-14`,
  `7.105427357601002e-15`, and `1.7763568394002505e-15`;
- curvature and regularization energy sums: `2.2737367544323206e-13` and
  `0.0`; and
- area and legacy-volume sums: `3.552713678800501e-15` and `0.0`.

All five repeats at every fixed thread count remain within the same fixed
`1e-10` absolute policy. Repeated clean-checkout runs exposed expected
last-bit scalar-reduction variation as small as `8.881784197001252e-16`, so
repeatability is deliberately tolerance-bound rather than claimed bit-exact.
Face-indexed publication, the independent Python aggregate, and the harness
aggregate each have maximum difference `0.0`. Measured reduction maxima are
reporting evidence rather than cross-platform exact constants.

## Boundary

Stock Option B serial/OpenMP accumulation and fixed-thread repeatability
evidence are complete. This does not claim scheduler assignment portability,
change production scheduling, approve stock scientific semantics, or make the
incomplete output contract acceptable.

Option B remains unselected, unrecommended, scientifically unapproved,
unimplemented, and unrouted. Output-visible evidence remains incomplete and
output-contract repair remains unauthorized. The remaining boundary is:

`review and explicitly authorize an output-contract repair lane; Option B remains unselected`.

Run the proof with:

```console
OPENSUBDIV_ROOT=/path/to/opensubdiv \
  ./scripts/run_irregular_valence5_option_b_serial_openmp.sh \
  --json --check --require-opensubdiv
```
