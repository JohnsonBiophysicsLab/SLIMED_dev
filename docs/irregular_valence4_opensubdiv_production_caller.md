# OpenSubdiv-Fed Valence-4 Production Caller Prerequisite

This lane closes the row-source gap left after the guarded OpenSubdiv row
provider. It remains an explicit reviewer-gated prerequisite and does not
activate a production route.

## Provider-Fed Caller

`evaluate_guarded_valence4_opensubdiv_production_caller(...)` composes two
previously separated guarded pieces:

- `build_guarded_opensubdiv_valence4_rows(...)` generates the complete
  `8 x 3 x 7 x 6` backend-neutral row package from OpenSubdiv; and
- `evaluate_guarded_valence4_production_caller_shadow(...)` runs the reviewed
  geometry/scientific atomic publication plus the shared production completion
  phase.

The function is default-off. Without
`reviewerApprovedExplicitCaller = true`, it rejects before calling the row
provider. With an explicit request, row generation must fully succeed before
the production caller shadow can validate destinations, clear current state,
publish geometry/scientific output, and run completion.

## Guarded Boundary

The provider-fed caller:

- rejects dependency-free builds through the existing row-provider gate;
- keeps all OpenSubdiv data behind backend-neutral source-keyed rows;
- leaves `Face::oneRingVertices` empty;
- does not enter `Mesh::Compute_Energy_And_Force()`;
- does not call the default evaluator membrane face loop;
- does not enable a production route; and
- preserves the existing default dependency and build-target behavior.

This is still not route activation. The default production evaluator remains
unchanged and cannot silently route valence-4 faces based on ambient
OpenSubdiv availability.

## Evidence

Focused C++ coverage requires default-off rejection without invoking the row
provider, explicit dependency-absent rejection without mutation, and
OpenSubdiv-present execution through the provider-fed caller with route flags
disabled.

The present-dependency wrapper compiles serial and OpenMP OpenSubdiv-enabled
harnesses and compares provider-fed caller output:

```text
provider_fed_production_caller: true
opensubdiv_row_provider_executed: true
opensubdiv_rows_generated: true
production_caller_shadow_executed: true
production_completion_phases_executed: true
serial_openmp_provider_fed_caller_parity_passed: true
production_route_enabled: false
actual_production_force_path_executed: false
production_face_loop_executed: false
production_one_rings_populated: false
```

This means route activation remains a separate reviewer/user decision. Default
dependency behavior, broader-valence routing, production formulas, scatter
semantics, OpenMP reduction policy, checkpoint/output, and propagation remain
unchanged.
