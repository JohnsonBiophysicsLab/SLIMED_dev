# Irregular Routing Evidence Gap Map

This is a docs/scripts-only planning note for the post-PR61 irregular
energy/force lane. It does not change production C++ behavior, default builds,
dependency policy, OpenSubdiv policy, force formulas, regular 12-control
behavior, scatter order, or broader valence support.

## Current Route Matrix

| Route | Current behavior | Current evidence | Remaining gap |
| --- | --- | --- | --- |
| Regular 12-control membrane force | Supported. | Regular evaluator, force formula, and scatter characterization tests. | Preserve serial/OpenMP baselines if a future backend changes row weights or force scatter. |
| 11-control `4+3+4` membrane force with `Param::subDivideTimes > 0` | Supported narrowly through existing subdivision matrices and transpose back-projection. | Synthetic 11-control area/volume and energy/force tests compare production output against independent test-side subdivision/back-projection. | Representative physical fixtures, serial/OpenMP tolerances, and production-data discovery. |
| 11-control membrane force with `Param::subDivideTimes <= 0` | Guarded unsupported. | Zero-depth diagnostic test verifies the route fails before regular fallback. | None for the current guard; changing this policy needs production review. |
| Other irregular force topologies | Unsupported. | Documentation explicitly limits support to the existing `11 = 4+3+4` matrix contract. | Backend or valence policy, fixtures, expected outputs, and review criteria. |
| OpenSubdiv-backed irregular replacement | Not production. | Existing OpenSubdiv docs/probe remain observational only. | Dependency/build policy, sample selection, source-id mapping, and force-formula equivalence. |

The machine-readable companion check is
`scripts/inventory_irregular_routing_evidence.py --check`. It records the
current support/guard/evidence anchors without parsing or executing production
C++.

The fixture-discovery companion check is
`scripts/inventory_irregular_fixture_candidates.py --check`, with the narrative
snapshot in `docs/irregular_fixture_discovery_report.md`. It inventories
checked-in face/vertex CSV meshes and a generated closed-valence-5 topology
probe without executing production C++.

## Evidence Gaps Worth Filling Next

1. Representative irregular fixtures beyond the synthetic 11-control patch.
   The next useful evidence is a fixture-discovery report or fixture generator
   that finds real non-ghost irregular faces in production-like meshes without
   changing setup behavior. The current discovery report adds the inert
   command and shows that checked-in mesh CSVs do not yet serialize a physical
   11-control fixture with explicit ghost status.

2. Serial/OpenMP tolerance policy for supported 11-control outputs. The
   evidence should compare area, volume, face curvature energy, normals, mean
   curvature, per-vertex force components, total energy, and force reductions
   under a stated tolerance instead of relying on the synthetic exact route
   comparison alone.

3. Unsupported-route inventory. Zero-depth 11-control requests are already
   guarded. Broader valence cases need a documented matrix of expected
   diagnostics before any route is broadened.

4. OpenSubdiv replacement criteria. Any backend lane should first define the
   derivative convention, ptex/sample plan, source-id map, back-projection
   shape, dependency policy, and regular equivalence tolerance. It should not
   be mixed with the representative-fixture evidence lane.

## Safe Follow-Up PR Shapes

- Docs/scripts-only fixture discovery: add an inert inventory command that
  scans checked-in or generated mesh fixtures and reports physical face
  one-ring sizes, ghost/boundary status, and candidate irregular faces.
- Tests-only tolerance characterization: add focused serial/OpenMP checks for
  the existing 11-control route using stable fixtures and explicit tolerances.
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
