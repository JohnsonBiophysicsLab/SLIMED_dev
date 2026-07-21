# OpenSubdiv Regular Executable Parity

This evidence lane compares complete evaluator-visible state for the disabled
double-row regular OpenSubdiv candidate. It is not production routing and does
not approve route activation.

The standalone harness compiles the real mesh and energy/force implementation
twice, once serially and once with the existing `OMP` accumulator. A dedicated
`SLIMED_OPENSUBDIV_REGULAR_EXECUTABLE_PARITY` compile definition allows only
those proof binaries to install candidate rows when
`SLIMED_USE_OPENSUBDIV_REGULAR=1` is also set. Ordinary builds do not define the
proof macro, so `kOpenSubdivRegularProductionRouteEnabled` remains `false`.

The wrapper executes four snapshots from the same deterministic periodic mesh:

- serial direct rows;
- serial candidate rows;
- OpenMP direct rows;
- OpenMP candidate rows.

The machine-readable comparison covers global and per-face energy components,
all per-vertex force components, active-face normals, area, legacy visible
volume, and mean curvature. It reports direct/candidate parity in each execution
mode and serial/OpenMP parity for both row sources under the existing `5e-6`
policy.

Run the absent-dependency check with:

```bash
env -u OPENSUBDIV_ROOT scripts/run_opensubdiv_regular_executable_parity.sh
```

Run the opt-in proof against an ABI-compatible OpenSubdiv prefix with:

```bash
OPENSUBDIV_ROOT=/path/to/opensubdiv \
scripts/run_opensubdiv_regular_executable_parity.sh --require-opensubdiv
```

A passing report closes the executable-output evidence gate only. Guarded
production activation remains a separate reviewer- and user-approved change.

On the deterministic periodic fixture, the candidate passed all four
comparisons. The largest direct-versus-candidate difference was
`4.656612873077393e-10` in global energy; the largest vertex-force difference
was `1.4551915228366852e-11`. The largest serial-versus-OpenMP difference was
`2.3283064365386963e-10` in global energy, with vertex forces at or below
`7.275957614183426e-12`. All reported channels remain well inside the unchanged
`5e-6` policy.
