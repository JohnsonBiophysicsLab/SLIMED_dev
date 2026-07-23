#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if ! command -v gsl-config >/dev/null 2>&1; then
    echo "gsl-config is required to compile the valence-5 fixture parity harness." >&2
    exit 3
fi

tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/slimed-irregular-valence5-parity.XXXXXX")"
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

common=(
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
    common+=("${flag}")
done
common+=(
    experiments/irregular_valence5_fixture_parity.cpp
    "${repo_sources[@]}"
)
for flag in $(gsl-config --libs); do
    common+=("${flag}")
done

serial_binary="${tmp_dir}/irregular_valence5_serial"
openmp_binary="${tmp_dir}/irregular_valence5_openmp"
"${common[@]}" -o "${serial_binary}"
"${common[@]}" -DOMP -fopenmp -o "${openmp_binary}"

"${serial_binary}" >"${tmp_dir}/serial.json"
OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}" \
    "${openmp_binary}" >"${tmp_dir}/openmp.json"

python3 scripts/compare_irregular_valence5_fixture_parity.py \
    --serial "${tmp_dir}/serial.json" \
    --openmp "${tmp_dir}/openmp.json"
