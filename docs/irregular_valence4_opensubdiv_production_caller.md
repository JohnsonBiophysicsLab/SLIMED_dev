# Guarded OpenSubdiv Valence-4 Production Face-Loop Caller

This lane closes the real face-loop evidence gap left after the guarded
OpenSubdiv row provider and production-caller completion shadow. It remains an
explicit reviewer-gated caller and does not activate a default production
route.

## Provider-Fed Caller

`evaluate_guarded_valence4_opensubdiv_production_face_loop_caller(...)`
composes the reviewed provider, geometry/scientific prevalidation, and shared
production membrane loop:

- `build_guarded_opensubdiv_valence4_rows(...)` generates the complete
  `8 x 3 x 7 x 6` backend-neutral row package from OpenSubdiv; and
- `execute_guarded_valence4_production_face_loop(...)` feeds prevalidated
  `7 x 6` shape matrices to the existing regular force algebra, existing
  production-shaped per-thread `source x 9` scatter, ascending-thread
  reduction, and shared completion phase.

The function is default-off. Without
`reviewerApprovedExplicitCaller = true`, it rejects before calling the row
provider. With an explicit request, it first requires the exact ordered `N=2`
quadrature sample plan and three exact `1/3` quadrature weights used to
generate the provider rows. Sample or weight drift rejects before the provider
or face loop executes and before any mesh-owned state is cleared. Row
generation, source mapping, geometry/scientific staging, destination
validation, and conversion to all per-face shape matrices must fully succeed
before the first mesh write or OpenMP face iteration.

## Guarded Boundary

The provider-fed caller:

- rejects dependency-free builds through the existing row-provider gate;
- keeps all OpenSubdiv data behind backend-neutral source-keyed rows;
- leaves `Face::oneRingVertices` empty;
- explicitly enters the shared production membrane face loop only through the
  guarded caller;
- exercises current regular force formulas, per-thread scatter, reduction,
  completion, total force/energy publication, and boundary handling;
- is not called by `Mesh::Compute_Energy_And_Force()` or any default
  evaluator path;
- does not enable a production route; and
- preserves the existing default dependency and build-target behavior.

This is still not route activation. The default production evaluator remains
unchanged and cannot silently route valence-4 faces based on ambient
OpenSubdiv availability.

## Evidence

Focused C++ coverage requires default-off rejection without invoking the row
provider, atomic sample/weight-drift rejection, explicit dependency-absent
rejection without mutation, and OpenSubdiv-present execution through the real
face-loop caller with route flags disabled.

The present-dependency wrapper compiles serial and OpenMP OpenSubdiv-enabled
harnesses and compares the real face-loop output with the reviewed completion
shadow and across serial/OpenMP builds:

```text
provider_fed_production_caller: true
exact_quadrature_sample_plan_validated: true
exact_quadrature_weights_validated: true
opensubdiv_row_provider_executed: true
opensubdiv_rows_generated: true
production_caller_shadow_executed: true
real_production_face_loop_caller: true
complete_transaction_validated_before_mutation: true
shadow_face_loop_parity_passed: true
production_completion_phases_executed: true
serial_openmp_provider_fed_caller_parity_passed: true
production_route_enabled: false
actual_production_force_path_executed: true
production_face_loop_executed: true
production_one_rings_populated: false
```

The measured serial/OpenMP force delta is required to remain within `1e-12`,
as is the real-loop versus reviewed-shadow delta. Route activation remains a
separate reviewer/user decision. Default dependency behavior,
broader-valence routing, production formulas, scatter semantics, OpenMP
reduction policy, checkpoint/output, and propagation remain unchanged.
