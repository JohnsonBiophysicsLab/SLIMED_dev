# SLIMED Refactor Workflow

This workflow is for small, reviewable refactor PRs. Refactor work should make
the next change safer without changing physics behavior, numerical algorithms,
Loop subdivision, boundary propagation, or dynamics propagation unless that
behavior change is the explicit goal of a later PR.

## Phase 0 Baseline Gate

Run the repo-local gate before opening a refactor PR:

```console
./scripts/verify_pr_ready.sh
```

The gate prints `git status --short`, then checks the supported Makefile build
and test targets:

- `make serial`
- `make omp`
- `make dyna`
- `make dyna_omp`
- `make test`
- `./bin/test_main`

The script runs `make clean` before each build target. The current Makefile
shares `obj/` and binary names between serial/OpenMP and continuum/dynamics
targets, so cleaning before each target prevents stale objects or executables
from making a mode look verified. The build and test commands run in a
temporary copy of the current working tree so that `make clean` cannot remove
tracked files or leave generated binaries in the developer checkout.

All required build and test modes are expected to compile under C++17. Expected
local tools are the existing project requirements: GNU Make, a C++17-capable
compiler, GSL with `gsl-config` on `PATH`, OpenMP support for the OpenMP
targets, and GoogleTest for `make test`. Current GoogleTest 1.17.x requires
C++17, so this baseline enables test modernization without vendoring or
upgrading GoogleTest in this PR. On macOS, the Makefile currently selects
`g++-15` for OpenMP builds.

### Post-PR10 Baseline Status

The post-PR10 baseline was refreshed from `origin/main` at
`4456e2383bd36fa2d462f68e10c37eb0cb71f32c`. The local GoogleTest discovery fix
remains in place: GoogleTest is scoped to `make test`, Homebrew `googletest`
and `libomp` include/library paths are detected for test builds, and test
objects are isolated under `obj/test/` so test builds do not reuse normal-mode
objects.

Verified on 2026-06-20 after the output/checkpoint cleanup merge
(`4456e2383bd36fa2d462f68e10c37eb0cb71f32c`):

- `make test` completed and linked `bin/test_main`.
- `./bin/test_main` passed 43 tests from 22 suites.
- `make -B serial` completed and linked `bin/continuum_membrane`.
- `./scripts/verify_pr_ready.sh` completed all 13 build/test steps.
- The committed example params, a checkpoint/restart smoke, the Fourier and
  boundary diagnostic CLIs/tests, and the OpenMP benchmark harness smoke all
  passed.
- The remaining post-PR10 warning buckets were removed: `BoundaryType::Fixed`
  is handled explicitly in the boundary-condition switches, and `Run_flat.cpp`
  no longer calls the deprecated `write_vertex_data_to_csv` wrapper.

Treat the full PR gate as the source of truth before marking later refactor work
ready. If warnings return in later baseline work, record the exact compiler,
target, and warning text here.

If a command fails because of local environment limits, record the exact command
and the relevant error output in the PR notes. Do not hide failures by removing
targets from the gate.

## Refactor PR Rules

- Keep changes small enough to review directly.
- Preserve existing output names and formats unless a PR is specifically about
  output migration.
- Do not commit generated build artifacts, simulation outputs, regenerated
  Doxygen HTML, or regenerated LaTeX.
- Prefer post-processing diagnostics for analysis-only validation.
- Add tests only where they protect behavior that the refactor touches.

## Energy/Force Evaluator Boundary

The first core-physics seam is `EnergyForceEvaluator`, a behavior-preserving
facade over `Mesh::Compute_Energy_And_Force()`. Its boundary is the current
mesh-state recomputation: element area and volume, current face energies,
current vertex force components/totals, `Param::energy`, optional scaffolding
energy/force contributions, and boundary/ghost force handling. Callers remain
responsible for previous-coordinate snapshots, previous-force/energy snapshots,
records, checkpoint state, optimizer state, RNG state, and propagation policy.

Keep future refactor slices on one side of this boundary at a time: either make
propagation/minimization call the evaluator more consistently, or split the
physics implementation behind it, but do not change numerical algorithms,
OpenMP scheduling, RNG behavior, Loop subdivision, or output/checkpoint formats
as part of evaluator plumbing.

For the post-PR20 propagation-mode map, see
`docs/propagation_mode_architecture.md`. That note records current
minimization, thermalized minimization, dynamics, checkpoint, output, and
record ownership before production separation work.

For the post-PR32 call-site inventory, see
`docs/energy_force_evaluator_callsite_inventory.md` and regenerate the source
classification with `python3 scripts/inventory_energy_force_call_sites.py`.
For the post-PR33 architecture cleanup candidate map, see
`docs/energy_force_evaluator_architecture_candidates.md` and include
`--helpers` when regenerating the local helper inventory.
For the post-PR35 internal evaluator side-effect map, see
`docs/energy_force_evaluator_side_effect_boundary.md` and regenerate the
write-surface inventory with
`python3 scripts/inventory_energy_force_side_effects.py`.

### Accepted-Step Minimization Smoke

Use the committed accepted-step smoke fixture when a refactor touches
`run_flat()` minimization evaluator plumbing or neighboring optimizer state:

```console
ROOT="$(pwd)"
WORKDIR=/tmp/slimed-accepted-step-smoke
make serial
python3 scripts/stage_accepted_step_smoke.py \
  --workdir "${WORKDIR}" \
  --force
(
  cd "${WORKDIR}"
  "${ROOT}/bin/continuum_membrane"
)
python3 scripts/check_accepted_step_smoke.py \
  "${WORKDIR}/EnergyForce.csv"
```

The staging helper copies `data/benchmark/accepted_step_minimization.params` to
`input.params` and copies the committed `data/COM.csv` scaffold into the same
scratch directory. The fixture enables existing harmonic scaffolding with
thermal fluctuations, meshpoint snapshots, XYZ output, and checkpoints disabled.
With `maxIterations = 2`, a successful run writes an initial `EnergyForce.csv`
row plus one post-initial finite row from the deterministic minimization branch.
That post-initial row is recorded after `run_flat()` accepts the line-search
step, applies the accepted displacement, refreshes energy and force through the
shared evaluator helper, and updates the caller-owned snapshots and record.

Keep generated smoke outputs in `/tmp` or another scratch directory. Do not
commit `EnergyForce.csv`, vertex snapshots, face snapshots, checkpoints, or log
captures from this smoke.

## Limit-Surface Evaluator Boundary

The first geometry seam is `LimitSurfaceEvaluator`, with the active
`SlimedLoopLimitSurfaceEvaluator` backend wrapping the current regular
12-control SLIMED Loop shape-function implementation. This boundary names the
per-sample position, first-derivative, second-derivative, and mixed-derivative
outputs needed by area, curvature, energy, and force code.

After PR #17, only the regular non-ghost `12 x 3` area/volume path in
`Mesh::calculate_element_area_volume()` is migrated to this evaluator. That
path must keep using cached `Param::shapeFunctions`, the existing OpenMP
reduction structure, and the legacy volume semantics, including
`0.16666666666`.

The next safe work is characterization, not production force migration:
regular shape-function products can be compared against evaluator outputs in
tests, and the geometry-extraction subset inside `element_energy_force_regular`
can be proven equivalent before force formulas run. Migrating that production
path requires a separate numerical-baseline PR because it is coupled to face
energy accumulation, force component construction, force scatter into
per-thread buffers, OpenMP reduction order, and global area/volume constraints.

For a future production energy/force evaluator migration, require a two-stage
baseline:

- Geometry-only checks must compare all seven regular rows from the evaluator
  against the current cached `shapeFunctions * 12 x 3 controlPoints` extraction
  for deterministic regular fixtures. Tests using the same SLIMED matrix helper
  should be exact; alternate arithmetic order or backend results need an
  explicit absolute/relative tolerance and recorded maximum deltas.
- Full energy/force checks must compare deterministic serial and OpenMP
  outputs for area, volume, face curvature energy, mean curvature, normals,
  per-vertex bending/area/volume/regularization/total forces, and total energy.
  The PR must state thread counts, compiler/platform, commands, and tolerance
  policy.
- Force scatter order through `face.oneRingVertices`, per-thread accumulation,
  OpenMP scheduling/reductions, boundary/ghost/periodic policy, output formats,
  checkpoint/restart-visible state, and legacy volume semantics must remain
  unchanged unless the PR is explicitly a numerical-behavior change.
- Stop instead of migrating if reviewable evidence would require exposing new
  production internals only for tests, duplicating the large force algorithm in
  tests, changing access boundaries, or making scientific tolerance decisions
  beyond isolated double-precision geometry equivalence.

Keep irregular `11 x 3` handling, boundary/ghost/periodic policy, dynamics
projection, OpenSubdiv dependency work, output/checkpoint formats, RNG behavior,
and volume-semantics changes out of evaluator-plumbing PRs unless the PR is
explicitly scoped to one of those topics and has its own baseline.

## Geometry And Limit-Surface Backlog

Irregular-patch energy/force routing is a separate geometry and numerical
correctness backlog, not an evaluator-phase extraction. Area/volume refresh
already distinguishes regular `12 = 4 + 4 + 4` one-ring patches from special
irregular `11 = 4 + 3 + 4` one-ring patches: regular faces use the current
limit-surface evaluator path, while `nOneRingVertices == 11` faces use the
existing subdivision matrices to enumerate regular subpatches for area and
volume.

Energy/force accumulation does not currently mirror that split. In the face
loop, the `nOneRingVertices == 11` branch still has a
`//@todo energy force irregular` comment and then calls
`element_energy_force_regular(...)`. Treat this as a known bug and backlog
item, not compatibility behavior. Existing committed models apparently do not
exercise irregular patches, which explains why baseline gates have stayed green
despite the wrong route.

The future work should stay staged and reviewable:

- First add an irregular-patch characterization fixture that exposes the
  current route and gives reviewers a deterministic geometry to discuss. The
  current fixture map lives in `docs/irregular_patch_fixture_requirements.md`;
  it adds geometry-only coverage for an explicit 11-control area/volume patch
  and keeps the known energy/force route gap documented rather than asserting
  on brittle source text or GSL failure behavior.
- Then decide the backend/design contract. Before expanding local
  case-by-case subdivision matrix code, decide whether OpenSubdiv or another
  limit-surface backend can unify regular and irregular Loop evaluation.
- Then make a focused production route fix for `nOneRingVertices == 11`,
  with serial/OpenMP numerical evidence and no unrelated evaluator cleanup.
- After that, broaden support beyond the current `12` and `11` one-ring cases
  where possible, or explicitly reject unsupported local geometry with
  diagnostics instead of falling through to the wrong evaluator.

A useful proof-of-concept reference is
https://github.com/Yibenfu/continuum_membrane_model/blob/main/myfunctions.cpp.
Do not copy code from it into SLIMED. The relevant idea to evaluate is an
`element_energy_force_irregular(...)` route that repeatedly subdivides an
11-point patch, evaluates regular subpatches, and back-projects subpatch forces
to the original irregular one-ring vertices through subdivision matrices.

## OpenMP Benchmark Harness

Use the lightweight benchmark harness to collect reproducible serial-vs-OpenMP
wall-time data before changing any OpenMP regions:

```console
python3 scripts/benchmark_openmp_scaling.py \
  --baseline-build-command "make serial" \
  --baseline-run-command "./bin/continuum_membrane" \
  --build-command "make omp" \
  --run-command "./bin/continuum_membrane" \
  --threads 1,2,4,8 \
  --repeats 3 \
  --csv /tmp/slimed-openmp-scaling.csv \
  --json /tmp/slimed-openmp-scaling.json
```

For dynamics runs, switch the build and executable commands to `make dyna`,
`make dyna_omp`, and `./bin/membrane_dynamics`. The current Makefile writes
both `make serial` and `make omp` to `bin/continuum_membrane`, and both
`make dyna` and `make dyna_omp` to `bin/membrane_dynamics`; the harness runs
the optional serial baseline build and measurements before rebuilding the
OpenMP target.

Use `--dry-run` to inspect the build/run sequence without executing commands or
writing outputs. A harmless smoke benchmark can use a tiny Python command:

```console
python3 scripts/benchmark_openmp_scaling.py \
  --run-command "python3 -c 'import time; time.sleep(0.01)'" \
  --threads 1,2 \
  --repeats 1 \
  --csv /tmp/slimed-openmp-smoke.csv \
  --json /tmp/slimed-openmp-smoke.json
```

The CSV records one row per measured command with the UTC date, git commit,
branch, detected compiler, `OMP_NUM_THREADS`, wall time, exit code, and optional
speedup/parallel efficiency. Speedup and efficiency are populated only when a
serial baseline command is provided. The optional JSON file includes the same
metadata plus aggregate mean/min/max/stdev timing summaries.

Do not commit generated benchmark CSV, JSON, or log files. Prefer `/tmp` paths
or another local scratch directory for all benchmark artifacts.

For the current local 1-10 thread scalability result and the 8-thread
recommendation for the post-PR30 scaffold workload, see
`docs/openmp_measurement_baseline.md`.

The committed example minimization exits successfully because the initial mean
force is already below the convergence threshold, so it is not a useful OpenMP
optimization workload. For real timing smoke tests, stage the benchmark-only
workload under `/tmp`:

```console
python3 scripts/stage_openmp_benchmark_workload.py \
  --workdir /tmp/slimed-openmp-benchmark-workload \
  --force
```

Then point the benchmark harness at wrapper commands that run
`continuum_membrane` from `/tmp/slimed-openmp-benchmark-workload`. The staged
input enables deterministic pure MMC thermal steps with a fixed seed and avoids
meshpoint, XYZ, and checkpoint outputs. The executable still writes standard
summary CSV files in its working directory, so keep the working directory under
`/tmp`.

Example smoke run:

```console
ROOT="$(pwd)"
WORKDIR=/tmp/slimed-openmp-benchmark-workload
OUTDIR=/tmp/slimed-openmp-meaningful-results

python3 scripts/benchmark_openmp_scaling.py \
  --baseline-build-command "/bin/zsh -lc 'make -C \"${ROOT}\" clean && make -C \"${ROOT}\" serial'" \
  --baseline-run-command "/bin/zsh -lc 'cd \"${WORKDIR}\" && \"${ROOT}/bin/continuum_membrane\"'" \
  --build-command "/bin/zsh -lc 'make -C \"${ROOT}\" clean && make -C \"${ROOT}\" omp'" \
  --run-command "/bin/zsh -lc 'cd \"${WORKDIR}\" && \"${ROOT}/bin/continuum_membrane\"'" \
  --threads 1,2 \
  --repeats 1 \
  --csv "${OUTDIR}/openmp-smoke.csv" \
  --json "${OUTDIR}/openmp-smoke.json" \
  --log-dir "${OUTDIR}/logs"
```

## Diagnostic Plan

Diagnostics should remain opt-in unless a later PR explicitly changes runtime
behavior. Prefer text-first post-processing outputs that can be attached to PRs
and compared in tests.

### Boundary Splitting Diagnostics

Use the existing boundary metadata before adding new runtime state. Dynamics
output can write typed vertices with coordinates, vertex type, and
`reflectiveVertexIndex`; that makes `vertex_type_begin.csv`,
`vertex_type_final.csv`, and optionally `face.csv` the natural inputs.

Run the text diagnostic:

```console
python3 analysis/boundary_split_diagnostics.py \
  --baseline-vertices vertex_type_begin.csv \
  --vertices vertex_type_final.csv \
  --faces face.csv \
  --output boundary_split_diagnostics.csv
```

The vertex CSV is parsed in the current SLIMED format:

```text
x,y,z,type,reflectiveVertexIndex,
```

The diagnostic tolerates spaces and trailing commas. Vertex types are reported
as:

- `0`: `Real`
- `1`: `FixedBoundary`
- `2`: `PeriodicBoundary`
- `3`: `PeriodicReflectiveBoundary`
- `4`: `Ghost`

The output CSV contains summary, duplicate-coordinate, reflective-pair,
suspected-split, and optional face-adjacency rows. Important record types:

- `invalid_reflective_index`: likely reflective indexing bug.
- `reflective_displacement_mismatch`: when `--baseline-vertices` is provided,
  the current-minus-baseline displacement differs from the reflective vertex
  displacement. This points to periodic post-processing or output-sync drift.
- `suspected_split_near_boundary`: close but non-coincident boundary/support
  rows at the configured tolerance, suggesting geometry or output drift near
  the boundary.
- `duplicate_coordinate_member`: stacked real/support/ghost rows. This often
  means a plot is drawing support rows as if they were membrane rows.
- `mixed_family_face`: a provided face row spans real/support/ghost families.
  This can make ghost/support geometry visible when plotting all faces.
- `interpretation`: a single high-level hint for the strongest observed signal.

Tune sensitivity with `--duplicate-tolerance` and `--split-tolerance`.

The parser fixture test is:

```console
python3 -m unittest tests/test_boundary_split_diagnostics.py
```

Optional plots should be explicit outputs in future tools, for example
`boundary_split_diagnostics.png`, and should not be required for the PR gate.

### Fourier-Space Membrane Modulation

Fourier verification should live as post-processing in `analysis/`, not in the
core C++ simulation path. Python analysis diagnostics should keep their tests
under `analysis/tests/` so the top-level `tests/` directory remains focused on
core C++ behavior.

Implementation status:

- PR #1, `Add Fourier membrane modulation diagnostic`, was merged and closed
  from the GitHub web UI on 2026-06-17.
- The merged post-processing CLI is `analysis/membrane_fourier_spectrum.py`.
- Its stdlib `unittest` coverage lives in
  `analysis/tests/test_membrane_fourier_spectrum.py`.

Supported CLI inputs:

- `--trajectory`
- `--outdir`
- `--start-frame`
- `--stride`
- `--grid-shape NX NY`
- `--spacing DX DY`
- `--plane {mean,tilt,none}`
- `--radial-bins`

The trajectory CSV rows are flattened timesteps:

```text
x0,y0,z0,x1,y1,z1,...
```

Existing writers may leave a trailing comma, so future parsers should tolerate
an empty final field.

Outputs are text-first and reviewable:

- `spectrum_raw.csv` with Fourier mode, q-vector magnitude, and power values
- `spectrum_radial.csv` with radial `S(q)` averages and counts
- `spectrum_summary.txt` with selected-frame and peak-mode summary metadata

The implementation uses only the Python standard library and computes a direct
2D DFT for small diagnostic fixtures. Keep optional scientific Python
dependencies guarded unless a later PR explicitly updates the project
requirements.
