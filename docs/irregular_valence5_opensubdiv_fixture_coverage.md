# Valence-5 OpenSubdiv Fixture Coverage Proof

The checked-in `data/fixtures/closed_valence5` icosahedron is already the
approved scientific stand-in for the supported positive-depth 11-control
route. This opt-in proof asks the narrower next question: can OpenSubdiv
evaluate finite value, first-derivative, and second-derivative limit stencils
over that exact serialized topology while preserving original source IDs?

Run the proof with:

```console
OPENSUBDIV_ROOT=/path/to/opensubdiv \
  scripts/run_irregular_valence5_opensubdiv_fixture_coverage.sh \
  --json --require-opensubdiv
```

Without `OPENSUBDIV_ROOT`, the wrapper exits successfully with a machine-readable
skip. With the dependency present, the probe loads the 12 serialized vertices
and 20 oriented faces, rejects any coordinate, face-order, or winding drift,
uses `s=v,t=w`, evaluates nine documented sample locations on every Ptex face,
and requires:

- all 180 requested samples to resolve and produce limit stencils;
- every source index and value/first/second-derivative coefficient to be valid
  and finite;
- all six value/derivative vectors evaluated from fixture coordinates to be
  finite for every one of the 180 samples;
- aggregate value, first-derivative, and second-derivative coverage of all
  original source IDs `0..11`; and
- byte-for-byte deterministic JSON across identical runs.

The proof is intentionally aggregate. A single sampled valence-5 face exposes
nine source IDs, while the all-face sample grid exposes all 12 fixture IDs.
This does not establish the per-face 11-control source order used by
`Face::oneRingVertices`, force-formula/back-projection parity, scatter or
OpenMP parity, or OpenSubdiv-backed valence-5 routing.

The output therefore keeps `proof_only:true`, `not_production_routing:true`,
`production_route_enabled:false`, and
`production_force_path_executed:false`. Default builds, the supported
dependency-free 11-control route, production formulas, scatter semantics,
OpenMP reductions, checkpoint/output, and propagation are unchanged.

The follow-up per-face source-order and weighted-transpose contract is recorded
in `docs/irregular_valence5_opensubdiv_source_order_transpose.md`. It locks the
production `20 x 11` source-slot order and proves source-keyed linear
back-projection through that duplicate scatter boundary. Actual
`fBend`/`fArea`/`fVolume` parity and production routing remain unproven and
unauthorized.

Production routing is not authorized.
