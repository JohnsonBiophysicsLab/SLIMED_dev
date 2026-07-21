#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

require_opensubdiv=0
for arg in "$@"; do
    if [[ "${arg}" == "--require-opensubdiv" ]]; then
        require_opensubdiv=1
    fi
done

emit_skip() {
    local reason=$1
    printf '{"status":"skipped","reason":"%s","not_production_routing":true}\n' "${reason}"
}

if [[ -z "${OPENSUBDIV_ROOT:-}" ]]; then
    emit_skip "OPENSUBDIV_ROOT is not set; executable parity is explicit opt-in only."
    [[ "${require_opensubdiv}" -eq 0 ]] || exit 2
    exit 0
fi

include_dir="${OPENSUBDIV_ROOT}/include"
if [[ ! -f "${include_dir}/opensubdiv/far/topologyDescriptor.h" ]]; then
    emit_skip "OpenSubdiv headers were not found under OPENSUBDIV_ROOT/include."
    [[ "${require_opensubdiv}" -eq 0 ]] || exit 2
    exit 0
fi

lib_dir=""
for candidate in "${OPENSUBDIV_ROOT}/lib" "${OPENSUBDIV_ROOT}/lib64"; do
    if compgen -G "${candidate}/libosdCPU.*" >/dev/null; then
        lib_dir="${candidate}"
        break
    fi
done
if [[ -z "${lib_dir}" ]]; then
    emit_skip "OpenSubdiv libosdCPU was not found under OPENSUBDIV_ROOT/lib or lib64."
    [[ "${require_opensubdiv}" -eq 0 ]] || exit 2
    exit 0
fi

if ! command -v gsl-config >/dev/null 2>&1; then
    echo "gsl-config is required to compile executable parity." >&2
    exit 3
fi

tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/slimed-opensubdiv-executable-parity.XXXXXX")"
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
    -DUSE_OPENSUBDIV_REGULAR
    -DSLIMED_OPENSUBDIV_REGULAR_EXECUTABLE_PARITY
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
if [[ -n "${OPENSUBDIV_CXXFLAGS:-}" ]]; then
    # shellcheck disable=SC2206
    extra_cxxflags=(${OPENSUBDIV_CXXFLAGS})
    common+=("${extra_cxxflags[@]}")
fi
common+=(
    experiments/opensubdiv_regular_executable_parity.cpp
    "${repo_sources[@]}"
    -I"${include_dir}"
    -L"${lib_dir}"
    "-Wl,-rpath,${lib_dir}"
)
if [[ -n "${OPENSUBDIV_LDFLAGS:-}" ]]; then
    # shellcheck disable=SC2206
    extra_ldflags=(${OPENSUBDIV_LDFLAGS})
    common+=("${extra_ldflags[@]}")
fi
common+=(-losdCPU)
for flag in $(gsl-config --libs); do
    common+=("${flag}")
done

serial_binary="${tmp_dir}/executable_parity_serial"
openmp_binary="${tmp_dir}/executable_parity_openmp"
"${common[@]}" -o "${serial_binary}"
"${common[@]}" -DOMP -fopenmp -o "${openmp_binary}"

env -u SLIMED_USE_OPENSUBDIV_REGULAR \
    "${serial_binary}" >"${tmp_dir}/serial-direct.json"
SLIMED_USE_OPENSUBDIV_REGULAR=1 \
    "${serial_binary}" >"${tmp_dir}/serial-candidate.json"
env -u SLIMED_USE_OPENSUBDIV_REGULAR OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}" \
    "${openmp_binary}" >"${tmp_dir}/openmp-direct.json"
SLIMED_USE_OPENSUBDIV_REGULAR=1 OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}" \
    "${openmp_binary}" >"${tmp_dir}/openmp-candidate.json"

python3 scripts/compare_opensubdiv_regular_executable_parity.py \
    --serial-direct "${tmp_dir}/serial-direct.json" \
    --serial-candidate "${tmp_dir}/serial-candidate.json" \
    --openmp-direct "${tmp_dir}/openmp-direct.json" \
    --openmp-candidate "${tmp_dir}/openmp-candidate.json"
