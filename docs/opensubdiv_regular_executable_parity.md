# OpenSubdiv Regular Executable Parity

This gate compares complete evaluator-visible state for the guarded regular
OpenSubdiv production route. The route exists only in an OpenSubdiv-enabled
binary and still requires explicit runtime opt-in.

The standalone harness compiles the real mesh and energy/force implementation
twice, once serially and once with the existing `OMP` accumulator. Both binaries
use the normal `USE_OPENSUBDIV_REGULAR` build gate. Candidate snapshots set
`SLIMED_USE_OPENSUBDIV_REGULAR=1`; direct snapshots omit it. Default builds
remain OpenSubdiv-free and cannot silently select this route.

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

A passing report verifies that the guarded production route remains within the
reviewed parity policy. The route also checks generated rows against the frozen
regular plan and leaves unsupported or non-equivalent faces on their existing
path. It does not establish irregular, boundary, ghost, or broader-valence
OpenSubdiv routing.

On the deterministic periodic fixture, the candidate passed all four
comparisons. The largest direct-versus-candidate difference was
`4.656612873077393e-10` in global energy; the largest vertex-force difference
was `1.4551915228366852e-11`. The largest serial-versus-OpenMP difference was
`2.3283064365386963e-10` in global energy, with vertex forces at or below
`7.275957614183426e-12`. All reported channels remain well inside the unchanged
`5e-6` policy. These values were reproduced before activation and remain the
acceptance envelope for the guarded route.
