# Valence-5 Alternate-Library Feasibility

## Scope

This observational, proof-only package executes the user-authorized Option D
investigation after PR #149. The authorization starts a bounded feasibility
survey; it does not rewrite PR #149 history or select an architecture. The
predecessor remains `predecessor_decision_selected:false` with
`predecessor_selected_option:null`.

The report also requires:

- `architecture_option_authorized_for_investigation:"D"`;
- `alternate_library_feasibility_lane_authorized:true`;
- `authorization_scope:"observational_feasibility_only"`;
- `investigation_authorization_is_architecture_selection:false`;
- `selected_library:null`;
- `library_selected:false`;
- `preferred_candidate:null`;
- `recommendation_present:false`;
- `dependency_policy_changed:false`;
- `production_route_enabled:false`;
- `scientifically_approved:false`;
- `patch_or_vendoring_performed:false`;
- `post_hoc_row_substitution_accepted:false`; and
- `normals_or_curvature_accepted_as_parametric_derivatives:false`; and
- `current_slimed_valence5_fallback_preserved:true`.

All four canonical PR #149 options remain historically `status:"unselected"`.
No library source is vendored and default tests make no network request. The
metadata below was retrieved from official documentation, release pages,
release archives, upstream repositories, and licenses on 2026-07-30.
OpenSubdiv is the predecessor/control and is not an alternate candidate.

## Required Contract

A viable replacement must satisfy all requirements together:

1. triangular Loop support at extraordinary valence;
2. exact limit-surface evaluation, not merely a finite refined mesh;
3. first and second parametric derivatives at extraordinary points;
4. a legitimate public custom mask, scheme, or evaluator seam;
5. evaluator-bound custom rows preserving the SLIMED valence-5 smooth mask
   (`neighbor_weight:0.075`, `center_weight:0.625`);
6. original source identity, order, cardinality, and duplicate semantics; and
7. chain-rule compatibility without patching, vendoring, or post-hoc row
   substitution.

Finite recursive refinement is recorded separately from exact limit
evaluation. A sparse refinement matrix, increasingly fine mesh, limit-vertex
weight helper, or tangent helper cannot by itself satisfy the face-point
limit/derivative contract.

## Frozen Candidate Set

The finite ordered set is exactly CGAL, libigl, OpenMesh, and pmp-library.
Missing, duplicate, reordered, or unknown candidates fail the report.
Geometry-central was considered while forming the set but excluded because
its documented "common subdivision" is an overlay of triangulations rather
than a Loop subdivision-surface evaluator.

### CGAL 6.2

- Release: [CGAL 6.2](https://www.cgal.org/2026/06/11/cgal62/), pinned commit
  `cac3e9d75e254928db0e38a3161564216cb01919`.
- License: package headers identify
  `LGPL-3.0-or-later OR LicenseRef-Commercial`; see the
  [CGAL license page](https://www.cgal.org/license.html).
- Compatibility/installability: C++17, header-oriented CMake package with
  documented dependencies.
- API: `Subdivision_method_3::PTQ` accepts a custom geometry mask. The
  [package manual](https://doc.cgal.org/latest/Subdivision_method_3/index.html)
  describes recursive refinement producing an "ever closer approximation".

Conclusion: CGAL has a real public custom *refinement* mask seam and general
Loop extraordinary support, but the reviewed package does not expose an exact
limit-surface face-point evaluator with first/second derivatives or an
evaluator-bound source/chain-rule contract.

### libigl 2.6.0

- Release: [v2.6.0](https://github.com/libigl/libigl/releases/tag/v2.6.0),
  pinned commit `40e7900ccbd767f1f360e0eb10f0f1a6432e0993`.
- License: [MPL-2.0](https://libigl.github.io/license/).
- Compatibility/installability: C++11 header-only core with CMake and Eigen.
- API: [`igl::loop`](https://libigl.github.io/dox/loop_8h.html) takes
  `number_of_subdivs`; an overload returns the sparse matrix for one
  refinement step.

Conclusion: the API supports fixed finite Loop refinement, including
extraordinary valence, but not exact limit evaluation, first/second
parametric derivatives, or a public custom evaluator seam.

### OpenMesh 11.0

- Release: [OpenMesh 11.0.0](https://www.graphics.rwth-aachen.de/software/openmesh/download/),
  official archive SHA-256
  `c7f35d29673e6dbb6d65b214c10c4c6249521a8f1e8f8db6e8bdc2eed798aedc`.
- Pinned upstream commit:
  `f13a3bf79f8dc91cd453b74baa9dc6f97a5a3062`.
- License:
  [BSD-3-Clause](https://www.graphics.rwth-aachen.de/software/openmesh/license/).
- Compatibility/installability: C++11 CMake library with documented Linux,
  Windows, and macOS support.
- API: `LoopT` performs finite uniform subdivision.
  `LoopSchemeMaskT` provides fixed original-Loop limit-position and two
  tangent weight families.

Conclusion: the helpers are closer to limit evidence, but they are fixed
vertex weights rather than an arbitrary face-point evaluator. The reviewed
release exposes no second parametric derivative API and no public
evaluator-bound custom seam preserving SLIMED's mask and source contract.

### pmp-library 3.0.0

- Release:
  [3.0.0](https://github.com/pmp-library/pmp-library/releases/tag/3.0.0),
  pinned commit `f2fb04f4a4188a5c1ab137e83b96e62fa99c639f`.
- License: [MIT](https://github.com/pmp-library/pmp-library/blob/f2fb04f4a4188a5c1ab137e83b96e62fa99c639f/LICENSE.txt).
- Compatibility/installability: C++17 compiled CMake library.
- API: [`pmp::loop_subdivision()`](https://www.pmp-library.org/subdivision.html)
  performs one in-place Loop refinement step.

Conclusion: the fixed refinement handles triangular extraordinary topology
but provides no reviewed exact limit/derivative evaluator or public custom
mask/scheme/evaluator seam.

The compatibility/installability entries above are source/documentation
observations. This lane did not install, compile, or link any candidate and
therefore reports `installability_not_executed:true`; it does not convert
documentation into a compile-validation claim.

## Result

All four candidates have documented C++ build/install paths and relevant mesh
capabilities, but installability was not executed or validated in this lane.
All four have `viable:false`; none satisfies the complete contract. The exact
blocker is:

`no viable candidate in the reviewed finite non-exhaustive set provides exact extraordinary Loop limit-surface evaluation with first and second parametric derivatives and a public evaluator-bound custom-mask seam that preserves the SLIMED valence-5 source and chain-rule contract`.

This is not a recommendation for or against future library work. It freezes
the reviewed evidence and preserves the current dependency-free SLIMED
positive-depth valence-5 fallback. New upstream evidence, or a separate
explicit architecture/scientific/dependency-policy decision, is required
before an alternate-library adapter or production route.
