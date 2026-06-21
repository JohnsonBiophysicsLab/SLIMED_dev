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

## Limit-Surface Evaluator Boundary

The first geometry seam is `LimitSurfaceEvaluator`, with the active
`SlimedLoopLimitSurfaceEvaluator` backend wrapping the current regular
12-control SLIMED Loop shape-function implementation. This boundary names the
per-sample position, first-derivative, second-derivative, and mixed-derivative
outputs needed by area, curvature, energy, and force code. It does not change
production call sites, irregular 11-control behavior, boundary/ghost policy,
dynamics projection, or dependency requirements. OpenSubdiv remains a future
opt-in backend after equivalence and dependency review.

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
