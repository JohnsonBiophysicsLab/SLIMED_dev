# Valence-5 OpenSubdiv Source-Order And Transpose Proof

This opt-in proof follows the aggregate fixture coverage established by PR
#143. It binds OpenSubdiv rows to the exact production topology contract for
the approved closed valence-5 icosahedron without enabling a route.

Run it with:

```console
OPENSUBDIV_ROOT=/path/to/opensubdiv \
  scripts/run_irregular_valence5_opensubdiv_source_order_transpose.sh \
  --json --require-opensubdiv
```

Without `OPENSUBDIV_ROOT`, the wrapper emits a successful machine-readable
skip. With the dependency present, it:

- loads the approved serialized fixture through production
  `Mesh::setup_from_vertices_faces()`;
- executes the existing dependency-free production reporter only to capture the
  current topology/source-order baseline;
- locks the canonical ordered `20 x 11` `Face::oneRingVertices` table;
- requires 11 slots, nine unique original source IDs, and exactly two duplicated source IDs for every face;
- evaluates OpenSubdiv value, first-derivative, and second-derivative rows for
  all 20 Ptex faces at the frozen three-point sample plan under `s=v,t=w`;
- requires each face's nine-source OpenSubdiv union to equal the unique source
  IDs in that production face's one-ring;
- checks the seven-row weighted identity
  `g dot (W p) == (W^T g) dot p` per face;
- independently recomputes the control-space dot product from the serialized
  double coordinates; and
- projects each source-keyed back-projection into the ordered 11 production
  slots with an asymmetric `1/3,2/3` duplicate split, then performs a
  proof-local re-aggregation that reconstructs the original source-keyed
  vector.

The reviewed tolerances separate the two numerical boundaries. The
OpenSubdiv-float versus serialized-double independent dot comparison uses
`5.0e-6`; the duplicate-slot re-scatter identity uses `1.0e-12`.

This is a source-order and linear-transpose proof only. It emits
`proof_only:true`, `not_production_routing:true`,
`production_route_enabled:false`, and
`production_scatter_executed:false`. The duplicate-slot reconstruction is
proof-local scatter-shape evidence; it does not invoke production scatter.
It also emits `opensubdiv_production_force_path_executed:false`. The separate
`existing_dependency_free_production_baseline_executed:true` field records
that the current production reporter supplied the baseline; it does not imply
that an OpenSubdiv production route ran. This proof does not compare actual
`fBend`, `fArea`, or `fVolume` rows against the positive-depth subdivision
matrix route, change production formulas or scatter, alter OpenMP reductions,
or enable valence-5 routing.

The successor force diagnostic now executes both force paths and finds that
direct whole-Ptex OpenSubdiv evaluation does not reproduce the existing
positive-depth `11 = 4+3+4` force composition. The completed child-domain
diagnostic confirms the six positive-depth domains and observes different
valence-5 extraordinary smooth-vertex masks, but does not prove that the mask
difference is causally sufficient for the residual. The completed
counterfactual capability diagnostic confirms that OpenSubdiv's public Loop
scheme API cannot construct that mask-only evaluator. The next boundary is an
explicitly reviewed custom OpenSubdiv Loop scheme or library decision.
