# Irregular Routing Evidence Gap Map

This is a docs/scripts-only planning note for the post-PR61 irregular
energy/force lane. It does not change production C++ behavior, default builds,
dependency policy, OpenSubdiv policy, force formulas, regular 12-control
behavior, scatter order, or broader valence support.

## Current Route Matrix

| Route | Current behavior | Current evidence | Remaining gap |
| --- | --- | --- | --- |
| Regular 12-control membrane force | Supported. | Regular evaluator, force formula, and scatter characterization tests. | Preserve serial/OpenMP baselines if a future backend changes row weights or force scatter. |
| 11-control `4+3+4` membrane force with `Param::subDivideTimes > 0` | Supported narrowly through existing subdivision matrices and transpose back-projection. | Synthetic 11-control area/volume and energy/force tests compare production output against independent test-side subdivision/back-projection. The serial/OpenMP tolerance lane now replays the documented thread-buffer reduction shape on deterministic synthetic route outputs. | Representative physical fixtures and executable-level serial/OpenMP baselines remain open until a stable production fixture exists. |
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

The serial/OpenMP tolerance companion check is
`scripts/inventory_irregular_serial_omp_tolerance.py --check`, with the
narrative snapshot in
`docs/irregular_serial_omp_tolerance_characterization.md`. It records the
current synthetic split-reduction tolerance envelope without changing
production OpenMP behavior.

## Evidence Gaps Worth Filling Next

1. Representative irregular fixtures beyond the synthetic 11-control patch.
   The next useful evidence is a fixture-discovery report or fixture generator
   that finds real non-ghost irregular faces in production-like meshes without
   changing setup behavior. The current discovery report adds the inert
   command and shows that checked-in mesh CSVs do not yet serialize a physical
   11-control fixture with explicit ghost status.

2. Serial/OpenMP tolerance policy for supported 11-control outputs. The
   synthetic reduction-order lane now compares area, volume,
   curvature-energy sums, and per-vertex curvature/area/volume force
   components under a stated tolerance. Face-local normals and mean curvature
   are still covered by the existing single-face route comparison; executable
   serial/OpenMP baselines remain blocked on a stable production irregular
   fixture.

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

The evidence standard should stay cautious. Synthetic route checks,
regular-equivalence reports, aggregate OpenSubdiv source coverage, and toy
transpose identities are mechanical evidence. They are not physics validation
unless a representative physical fixture exists and passes a reviewed
comparison plan.

## Safe Follow-Up PR Shapes

- Docs/scripts-only fixture discovery: add an inert inventory command that
  scans checked-in or generated mesh fixtures and reports physical face
  one-ring sizes, ghost/boundary status, and candidate irregular faces.
- Tests-only tolerance characterization: extend the synthetic
  serial/OpenMP-compatible reduction checks only after a stable fixture or
  explicit scientific fixture decision exists.
- Docs-only backend criteria: refine the OpenSubdiv replacement checklist after
  a dependency policy decision, without adding build files or production
  routing.

## Recommended Next Prompt

```text
Add a docs/scripts-only irregular fixture discovery report for SLIMED. Do not
change production C++ behavior, build files, dependencies, OpenSubdiv policy,
or broader valence support. Inventory checked-in/generated meshes for
non-ghost irregular faces, record face one-ring sizes and boundary/ghost status,
and map any candidate fixtures to the existing supported/guarded irregular
route matrix. Validate with Python compile/checks, git diff --check, make test,
./bin/test_main if feasible, and focused irregular route filters.
```
