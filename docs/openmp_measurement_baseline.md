# OpenMP Measurement Baseline

This note records the first OpenMP measurement pass after the post-PR11
baseline. It is intentionally measurement-only: no source optimization was made
because the committed example workload is too short for a reliable optimization
decision.

## Baseline

- Date: 2026-06-20
- Commit: `51795a472443cb4a41c5a72db188ec5714e0444d`
- Branch: `codex/openmp-measurement-first-optimization`
- Compiler detected by the harness: `g++-15 (Homebrew GCC 15.2.0_1) 15.2.0`
- Build modes checked with clean object directories:
  - `make serial`
  - `make omp`
  - `make dyna`
  - `make dyna_omp`

The Makefile writes serial and OpenMP builds to the same object and executable
paths. For measurements that build both modes in one harness run, use wrapper
commands that run `make clean` before each build. Otherwise, `make omp` can
reuse serial objects and under-measure the actual OpenMP build.

## Benchmark Method

The run used `data/example/example.params` copied to
`/tmp/slimed-openmp-benchmark/input.params`, with these local-only edits:

- `maxIterations = 20`
- `meshpointOutput = false`
- `xyzOutput = false`

The benchmark wrote CSV, JSON, and logs under `/tmp/slimed-openmp-results`.
Generated benchmark files and simulation outputs are not committed.

```console
python3 scripts/benchmark_openmp_scaling.py --help

python3 scripts/benchmark_openmp_scaling.py \
  --baseline-build-command /tmp/slimed-openmp-benchmark/build_serial_clean.sh \
  --baseline-run-command /tmp/slimed-openmp-benchmark/run_continuum_tmp.sh \
  --build-command /tmp/slimed-openmp-benchmark/build_omp_clean.sh \
  --run-command /tmp/slimed-openmp-benchmark/run_continuum_tmp.sh \
  --threads 1,2,4 \
  --repeats 1 \
  --csv /tmp/slimed-openmp-results/dry-run.csv \
  --json /tmp/slimed-openmp-results/dry-run.json \
  --log-dir /tmp/slimed-openmp-results/logs-dry \
  --dry-run

python3 scripts/benchmark_openmp_scaling.py \
  --baseline-build-command /tmp/slimed-openmp-benchmark/build_serial_clean.sh \
  --baseline-run-command /tmp/slimed-openmp-benchmark/run_continuum_tmp.sh \
  --build-command /tmp/slimed-openmp-benchmark/build_omp_clean.sh \
  --run-command /tmp/slimed-openmp-benchmark/run_continuum_tmp.sh \
  --threads 1,2,4 \
  --repeats 3 \
  --csv /tmp/slimed-openmp-results/openmp-scaling.csv \
  --json /tmp/slimed-openmp-results/openmp-scaling.json \
  --log-dir /tmp/slimed-openmp-results/logs
```

The wrapper scripts used by the harness were local scratch files under `/tmp`:

```console
# /tmp/slimed-openmp-benchmark/build_serial_clean.sh
make -C /Users/yueying/.codex/worktrees/28fd/SLIMED_dev clean
make -C /Users/yueying/.codex/worktrees/28fd/SLIMED_dev serial

# /tmp/slimed-openmp-benchmark/build_omp_clean.sh
make -C /Users/yueying/.codex/worktrees/28fd/SLIMED_dev clean
make -C /Users/yueying/.codex/worktrees/28fd/SLIMED_dev omp

# /tmp/slimed-openmp-benchmark/run_continuum_tmp.sh
cd /tmp/slimed-openmp-benchmark
exec /Users/yueying/.codex/worktrees/28fd/SLIMED_dev/bin/continuum_membrane
```

## Results

The harness completed successfully. The committed example input stops at step 0
because the initial mean force is already below the convergence threshold, so
these numbers mostly measure setup plus one energy/force evaluation.

| Phase | Threads | Mean wall seconds | Min | Max | Speedup | Efficiency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Serial baseline | 1 | 0.288045 | 0.169584 | 0.523950 | 1.000 | 1.000 |
| OpenMP | 1 | 0.241834 | 0.169730 | 0.377539 | 1.191 | 1.191 |
| OpenMP | 2 | 0.128107 | 0.127002 | 0.130047 | 2.248 | 1.124 |
| OpenMP | 4 | 0.112688 | 0.112381 | 0.113182 | 2.556 | 0.639 |

The first serial and first OpenMP repeat were much slower than later repeats,
which makes the three-repeat mean noisy. Excluding first-run warmup effects, the
serial and OpenMP one-thread runs are both about 0.17 seconds, two OpenMP
threads are about 0.128 seconds, and four OpenMP threads are about 0.113
seconds. That suggests some parallel benefit, but the workload is too small to
judge optimization priorities.

## OpenMP Region Assessment

Likely continuum hot regions are in `Mesh::Compute_Energy_And_Force()` and
`Mesh::energy_force_regularization()` in
`src/energy_force/Compute_energy_and_force_on_mesh.cpp`. These loops already
avoid direct force races by accumulating into per-thread buffers, then reducing
back to vertices. The likely cost centers are:

- Per-call allocation of `faceForceComponents` and `fRegComponents`, sized by
  `omp_get_max_threads()` and vertex count.
- Per-face `Matrix` allocation/free inside OpenMP loops for one-ring geometry
  and force components.
- Serial face-energy accumulation after per-face energy calculation.

Those are plausible optimization targets, but changing them could alter
floating-point summation order, memory ownership, or force accumulation behavior.
A source optimization should wait for a benchmark input that performs multiple
nontrivial minimization iterations and a serial-vs-OpenMP numerical comparison.

The dynamics loop in `src/dynamics/Dynamic_model.cpp` has a higher correctness
risk: `DynamicModel::next_step()` shares a random generator and normal
distribution across an OpenMP parallel loop. Fixing that would change random
number generation order and therefore numerical trajectories, so it needs
scientific review and explicit tolerance criteria before implementation.

## First Optimization Target

No local low-risk optimization is recommended from this pass. The next
optimization PR should first establish a deterministic benchmark that does not
converge at step 0, then compare serial and OpenMP outputs within an explicit
tolerance. Once that exists, the first continuum target should be the
energy/force accumulation path, especially the per-call per-thread buffers and
per-face matrix allocations.

## Follow-up Benchmark Workload

`data/benchmark/openmp_pure_mmc.params` is a benchmark-only workload derived
from `data/example/example.params`. It does not change C++ behavior or the
committed example input. Instead, it enables the existing pure MMC thermal mode
with a fixed seed so a short benchmark performs deterministic repeated
energy/force evaluations rather than exiting at step 0. The fixture disables
meshpoint, XYZ, and checkpoint outputs, but the executable still writes its
standard summary CSV files, so run it from a scratch directory.

Stage the workload under `/tmp`:

```console
python3 scripts/stage_openmp_benchmark_workload.py \
  --workdir /tmp/slimed-openmp-benchmark-workload \
  --force
```

Then use wrapper commands that clean before switching build modes and execute
the binary from that scratch directory. The benchmark CSV, JSON, logs, and
simulation outputs should all remain under `/tmp`.

For a short serial-vs-OpenMP smoke run from the repository root:

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

On 2026-06-20, this smoke workflow completed and each serial/OpenMP log
recorded steps 1 through 7.

## Post-PR30 1-10 Thread Sweep

A follow-up sweep after PR #30 measured the OpenMP continuum minimization path
on a larger, scaffold-forced local workload. This was still a measurement-only
pass: no production source, Makefile behavior, OpenMP schedule, numerical
algorithm, RNG behavior, or output format was changed.

- Date: 2026-06-22
- Commit: `06b35bcf260828131070ab1c58758b8b56553833`
- Hardware: 10 logical CPUs total, described locally as 8 performance-core
  threads plus 2 efficiency-core threads, with no SMT.
- Workload: fixed 3 minimization steps (`maxIterations = 4`) on a
  50 nm x 50 nm membrane with scaffold forcing from `data/csv/GagR50_22.csv`.
- Completion: all serial and OpenMP runs completed exactly 3 minimization
  steps.
- Local artifacts: the ad hoc run wrote CSV and JSON under
  `/tmp/slimed_omp_scaling`. Those generated outputs are intentionally not
  committed.

| Phase | Threads | Mean wall seconds | Min | Max | Speedup vs serial |
| --- | ---: | ---: | ---: | ---: | ---: |
| Serial baseline | 1 | 2.896 | 2.827 | 3.006 | 1.000 |
| OpenMP | 1 | 2.944 | 2.883 | 3.060 | 0.984 |
| OpenMP | 2 | 1.636 | 1.627 | 1.649 | 1.771 |
| OpenMP | 3 | 2.054 | 2.047 | 2.065 | 1.410 |
| OpenMP | 4 | 1.636 | 1.632 | 1.642 | 1.770 |
| OpenMP | 5 | 1.325 | 1.305 | 1.342 | 2.186 |
| OpenMP | 6 | 1.336 | 1.333 | 1.338 | 2.169 |
| OpenMP | 7 | 1.350 | 1.329 | 1.373 | 2.146 |
| OpenMP | 8 | 1.181 | 1.171 | 1.186 | 2.453 |
| OpenMP | 9 | 1.315 | 1.308 | 1.318 | 2.203 |
| OpenMP | 10 | 1.207 | 1.195 | 1.219 | 2.399 |

The best mean wall time in this sweep was at 8 OpenMP threads. Using all 10
hardware threads still worked and remained close to the best result, but was
slightly slower than 8 for this machine and workload. The current local
recommendation for this benchmark shape is therefore to cap measurement runs at
8 OpenMP threads when comparing against this machine. Treat this as
machine/workload-specific evidence, not a universal hard cap for SLIMED.

To reproduce a comparable sweep, stage a scratch `input.params` under `/tmp`
with the workload properties above, keep generated simulation outputs in that
scratch directory, and run the harness with a full 1-10 thread list:

```console
ROOT="$(pwd)"
WORKDIR=/tmp/slimed-omp-50nm-scaffold-workload
OUTDIR=/tmp/slimed_omp_scaling

python3 scripts/benchmark_openmp_scaling.py \
  --baseline-build-command "/bin/zsh -lc 'make -C \"${ROOT}\" clean && make -C \"${ROOT}\" serial'" \
  --baseline-run-command "/bin/zsh -lc 'cd \"${WORKDIR}\" && \"${ROOT}/bin/continuum_membrane\"'" \
  --build-command "/bin/zsh -lc 'make -C \"${ROOT}\" clean && make -C \"${ROOT}\" omp'" \
  --run-command "/bin/zsh -lc 'cd \"${WORKDIR}\" && \"${ROOT}/bin/continuum_membrane\"'" \
  --threads 1,2,3,4,5,6,7,8,9,10 \
  --repeats 3 \
  --csv "${OUTDIR}/openmp_sweep_1_10.csv" \
  --json "${OUTDIR}/openmp_sweep_1_10.json" \
  --log-dir "${OUTDIR}/logs"
```

If the staged params use a relative `scaffoldingFileName`, copy or symlink the
scaffold CSV into the scratch workload directory; otherwise use an absolute
path to the repository's `data/csv/GagR50_22.csv`.
