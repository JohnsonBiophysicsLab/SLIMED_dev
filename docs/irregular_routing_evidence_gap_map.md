# Irregular Routing Evidence Gap Map

This is a docs/scripts-only planning note for the post-PR61 irregular
energy/force lane. It does not change production C++ behavior, default builds,
dependency policy, OpenSubdiv policy, force formulas, regular 12-control
behavior, scatter order, or broader valence support.

## Current Route Matrix

| Route | Current behavior | Current evidence | Remaining gap |
| --- | --- | --- | --- |
| Regular 12-control membrane force | Supported. | Regular evaluator, force formula, and scatter characterization tests. | Preserve serial/OpenMP baselines if a future backend changes row weights or force scatter. |
| 11-control `4+3+4` membrane force with `Param::subDivideTimes > 0` | Supported narrowly through existing subdivision matrices and transpose back-projection. | Synthetic route tests plus the approved closed valence-5 stand-in exercise all 20 physical faces through production setup. Actual serial/OpenMP executables compare energy, force, normals, area, legacy volume, and mean curvature within `1.0e-10`. | Preserve the fixture and tolerance baselines; no narrow route evidence gap remains. |
| 11-control membrane force with `Param::subDivideTimes <= 0` | Guarded unsupported. | Zero-depth diagnostic test verifies the route fails before regular fallback. | None for the current guard; changing this policy needs production review. |
| Other irregular force topologies | Unsupported. | Documentation explicitly limits support to the existing `11 = 4+3+4` matrix contract. | Backend or valence policy, fixtures, expected outputs, and review criteria. |
| OpenSubdiv-backed irregular replacement | Not production. | Existing OpenSubdiv docs/probe remain observational only. | Dependency/build policy, sample selection, source-id mapping, and force-formula equivalence. |

The supported positive-depth 11-control route and a future OpenSubdiv backend
replacement are intentionally separate rows. The supported route uses existing
subdivision matrices and transpose back-projection; it does not add a
dependency, change build/install policy, broaden valence support, or validate
OpenSubdiv routing.

The machine-readable companion check is
`scripts/inventory_irregular_routing_evidence.py --check`. It records the
current support/guard/evidence anchors without parsing or executing production
C++.

The fixture-discovery companion check is
`scripts/inventory_irregular_fixture_candidates.py --check`, with the narrative
snapshot in `docs/irregular_fixture_discovery_report.md`. It inventories
checked-in face/vertex CSV meshes and a generated closed-valence-5 topology
probe without executing production C++.

The approved `data/example` physical mesh is now also exercised through
production `Mesh::setup_from_vertices_faces()` by
`SurfaceIrregularFixtureCharacterization.ApprovedExampleMeshHasNoPhysicalIrregularFaceAfterProductionSetup`.
The result is negative but definitive: all 2,720 physical faces are regular,
and all 336 mixed-valence faces belong to the 960-face periodic ghost band.

The serial/OpenMP tolerance companion check is
`scripts/inventory_irregular_serial_omp_tolerance.py --check`, with the
narrative snapshot in
`docs/irregular_serial_omp_tolerance_characterization.md`. It records the
synthetic split-reduction envelope and the approved closed valence-5 actual
serial/OpenMP executable comparison without changing production OpenMP
behavior.

## Evidence Gaps Worth Filling Next

1. Broader-valence representative fixtures. The narrow positive-depth
   11-control fixture gate is resolved by the approved serialized closed
   valence-5 stand-in. Unsupported broader valences still need their own
   reviewed coordinates, route contract, and scientific expectations.

2. Preserve the supported 11-control executable baseline. The approved stand-in
   now covers energy, all force components, normals, area, legacy volume, and
   mean curvature in actual serial/OpenMP builds with a maximum observed delta
   of `1.4210854715202004e-14` under the `1.0e-10` policy.

3. Unsupported-route inventory. Zero-depth 11-control requests are already
   guarded. Broader valence cases need a documented matrix of expected
   diagnostics before any route is broadened.

4. OpenSubdiv replacement criteria. Any backend lane should first satisfy the
   consolidated criteria in
   `docs/opensubdiv_backend_interface_policy.md`: physical fixture
   availability, derivative and coordinate conventions, ptex/sample coverage
   plan, source-id mapping, transpose/back-projection shape, regular
   equivalence tolerance, serial/OpenMP comparison tolerance,
   dependency/build/install/vendoring policy, backend interface ownership,
   reviewer and scientific signoff, and rollback/fallback behavior. It should
   not be mixed with the representative-fixture evidence lane.

The evidence standard should stay cautious. The approved stand-in resolves the
narrow 11-control claim only. Synthetic route checks,
regular-equivalence reports, aggregate OpenSubdiv source coverage, and toy
transpose identities are mechanical evidence. They are not physics validation
for unsupported broader valences or an OpenSubdiv irregular route without a
separate representative fixture and reviewed comparison plan.

## Safe Follow-Up PR Shapes

- Docs/scripts-only broader-valence inventory: record exact unsupported
  one-ring shapes and diagnostics without changing routing.
- Tests/experiments-only preservation: retain the approved 11-control fixture
  and serial/OpenMP executable comparison as regression gates.
- Docs-only backend criteria: refine the OpenSubdiv replacement checklist after
  a dependency policy decision, without adding build files or production
  routing.

## Recommended Next Prompt

```text
Inventory the exact unsupported broader-valence one-ring shapes and current
diagnostics without enabling a route. Keep the approved closed valence-5
fixture as the regression gate for the existing narrow 11-control path. Do not
change routing, formulas, default dependencies, OpenMP reductions,
checkpoint/output, or propagation in the inventory lane.
```
