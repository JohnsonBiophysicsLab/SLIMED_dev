#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -z "${OPENSUBDIV_ROOT:-}" ]]; then
    if [[ " $* " == *" --json "* ]]; then
        printf '%s\n' '{"status":"skipped","reason":"OPENSUBDIV_ROOT is not set; Option B assessment is opt-in only."}'
    else
        echo "status: skipped"
        echo "reason: OPENSUBDIV_ROOT is not set; Option B assessment is opt-in only."
    fi
    if [[ " $* " == *" --require-opensubdiv "* ]]; then
        exit 2
    fi
    exit 0
fi

tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/slimed-option-b-assessment.XXXXXX")"
cleanup() {
    rm -rf "${tmp_dir}"
}
trap cleanup EXIT

./scripts/run_irregular_valence5_opensubdiv_force_parity.sh \
    --json --require-opensubdiv >"${tmp_dir}/force.json"
./scripts/run_irregular_valence5_opensubdiv_integration_composition.sh \
    --json --require-opensubdiv >"${tmp_dir}/composition.json"
./scripts/run_irregular_valence5_fixture_parity.sh \
    --json --check >"${tmp_dir}/current-serial-openmp.json"

forwarded=()
for argument in "$@"; do
    if [[ "${argument}" != "--require-opensubdiv" ]]; then
        forwarded+=("${argument}")
    fi
done

python3 scripts/run_irregular_valence5_option_b_scientific_rebaseline_assessment.py \
    --force-report "${tmp_dir}/force.json" \
    --composition-report "${tmp_dir}/composition.json" \
    --current-serial-openmp-report "${tmp_dir}/current-serial-openmp.json" \
    "${forwarded[@]}"
