#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

want_json=0
require_opensubdiv=0
for arg in "$@"; do
    [[ "${arg}" == "--json" ]] && want_json=1
    [[ "${arg}" == "--require-opensubdiv" ]] && require_opensubdiv=1
done

if [[ -z "${OPENSUBDIV_ROOT:-}" ]]; then
    if [[ "${want_json}" -eq 1 ]]; then
        printf '{"reason":"OPENSUBDIV_ROOT is not set; proof is opt-in only.",'
        printf '"status":"skipped"}\n'
    else
        echo "status: skipped"
        echo "reason: OPENSUBDIV_ROOT is not set; proof is opt-in only."
    fi
    [[ "${require_opensubdiv}" -eq 1 ]] && exit 2
    exit 0
fi

if ! command -v gsl-config >/dev/null 2>&1; then
    echo "gsl-config is required for the production source-order reporter." >&2
    exit 3
fi

tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/slimed-val5-source-transpose.XXXXXX")"
cleanup() {
    rm -rf "${tmp_dir}"
}
trap cleanup EXIT

repo_sources=()
while IFS= read -r source; do
    repo_sources+=("${source}")
done < <(find src -name '*.cpp' \
    ! -name 'Run_flat.cpp' \
    ! -name 'Run_dynamics_flat.cpp' \
    | sort)

if [[ -n "${CXX:-}" ]]; then
    cxx="${CXX}"
elif [[ "$(uname -s)" == "Darwin" ]] && command -v g++-15 >/dev/null 2>&1; then
    cxx="g++-15"
else
    cxx="c++"
fi

compile=(
    "${cxx}"
    -std=c++17
    -Iinclude
    -Iinclude/energy_force
    -Iinclude/linalg
    -Iinclude/mesh
    -Iinclude/model
    -Iinclude/parameters
)
for flag in $(gsl-config --cflags); do
    compile+=("${flag}")
done
compile+=(
    experiments/irregular_valence5_fixture_parity.cpp
    "${repo_sources[@]}"
)
for flag in $(gsl-config --libs); do
    compile+=("${flag}")
done
compile+=(-o "${tmp_dir}/production_reporter")
"${compile[@]}"
"${tmp_dir}/production_reporter" >"${tmp_dir}/production.json"

scripts/run_opensubdiv_probe.sh \
    --json \
    --require-opensubdiv \
    --valence5-source-order-transpose-report \
    >"${tmp_dir}/opensubdiv.json"

python3 scripts/compare_irregular_valence5_opensubdiv_source_order_transpose.py \
    --production "${tmp_dir}/production.json" \
    --opensubdiv "${tmp_dir}/opensubdiv.json" \
    --vertices data/fixtures/closed_valence5/vertices.csv
