# Valence-3 PR 176/182 archival evidence

Date: 2026-08-06

Status: evidence-only archive for D0; no production authorization

Archive PR base: merged PR 191 at
`617f422ae3b03ac1b7dee7ab0b8aeafc532d8be2`

## Immutable stack references

- PR 176 production-root head `46c06080fb663bcb43f38cf32fc1b45daa8732e8`
  is preserved by tag `archive/valence3-pr176-46c0608`.
- PR 182 convergence-evidence leaf
  `9587e3dce4509029e611e2937bac570b410193c3` is preserved by tag
  `archive/valence3-pr182-9587e3d`.
- PR 182 is stacked directly on the tagged PR 176 head. Neither tag marks a
  production baseline or an approved generic Loop implementation.

The tags retain the complete historical implementations, runners, documents,
and evidence. This small archive imports only the two reusable candidate
fixtures:

- `data/fixtures/candidates/closed_valence3_triangular_bipyramid` from the
  PR 176 tag; and
- `data/fixtures/candidates/asymmetric_valence3_triangular_bipyramid` from the
  PR 182 tag.

Both metadata files remain `candidate_only`, `proof_only`, and
`not_production_routing`. The symmetric and asymmetric meshes are closed,
outward-oriented triangular bipyramids with face-valence triplet `3/4/4`.

The baseline inventory binds the imported bytes:

| fixture file | SHA-256 |
| --- | --- |
| `asymmetric_valence3_triangular_bipyramid/candidate_metadata.json` | `4c3c2a8f66ad63a42c8c39b38d5fa776b2abff82fdaef9e8345fce3ee90b77c1` |
| `asymmetric_valence3_triangular_bipyramid/faces.csv` | `8015f9a4f4cb658390149c9fa06104e5eb5936dfffa0f99b919fe0aee05a1203` |
| `asymmetric_valence3_triangular_bipyramid/vertices.csv` | `a94f9f70e8a3932e96dfc4169b2da3825a27ba62c387b7c5a1c68847752d9705` |
| `closed_valence3_triangular_bipyramid/candidate_metadata.json` | `10e219c89c7ae662c5e6d0125b6b0e818da363d10eb9a59b389107f1f49c0420` |
| `closed_valence3_triangular_bipyramid/faces.csv` | `8015f9a4f4cb658390149c9fa06104e5eb5936dfffa0f99b919fe0aee05a1203` |
| `closed_valence3_triangular_bipyramid/vertices.csv` | `d48ab492eb43ec7b208dc112079f5818aef1a8104fb5d873ba43faa0d9641f2b` |

## Historical result and its limits

The tagged PR 182 study used OpenSubdiv 3.7.0, isolation level 5, a nested
three-interior-point rule at depths 0 through 4, and the fixed parameters
recorded in that tag. It reported that neither fixture met its last-two-step
global `1e-6` and per-source force `1e-5` activation targets. At depth 3 to 4,
the recorded global/force changes were:

| fixture | global change | force change |
| --- | ---: | ---: |
| symmetric | `2.3286725851e-4` | `1.2813709798e-3` |
| asymmetric | `2.3772548947e-4` | `1.5142500944e-2` |

This is scoped historical negative evidence, not a current convergence oracle.
It establishes no conclusion for other topologies, deeper levels, other
quadrature families, or stock Loop generally. It does not authorize merging
the per-valence production route from PR 176.

## WP5.1 handoff

WP5.1 must consume the two archived fixtures through the generic proof
interface and independently re-derive convergence evidence. It must test the
predeclared uniform, higher-order symmetric, graded-corner, and patch-domain
candidate families under the current frozen oracle and tolerance rules. The
tagged PR 182 numbers may be reported as historical comparison values but may
not be copied as the new oracle or used to skip reproduction.

## D0 authority and ordered disposition

On 2026-08-06, before either open PR was changed, the user explicitly decided
D0 and ordered this sequence:

1. tag and push the exact PR 176 and PR 182 heads;
2. merge one small archive PR containing both fixtures and this note;
3. only then close PR 176 and PR 182 as superseded, referencing the tags and
   this note; and
4. record the completed disposition in the ADR ledger, with WP5.1 consuming
   the fixtures and independently re-deriving the convergence result.

This section records the explicit user authority before closure. The final ADR
edit in step 4 synchronizes the ledger with the completed disposition; it does
not provide retroactive authority. PR 176 and PR 182 remain open until this
archive reaches `main`.
