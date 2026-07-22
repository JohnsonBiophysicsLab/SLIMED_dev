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
    printf '{"kind":"test_only_opensubdiv_regular_cache_prototype","not_production_cache":true,"reason":"%s","status":"skipped"}\n' "${reason}"
}

if [[ -z "${OPENSUBDIV_ROOT:-}" ]]; then
    emit_skip "OPENSUBDIV_ROOT is not set"
    [[ "${require_opensubdiv}" -eq 0 ]] || exit 2
    exit 0
fi

include_dir="${OPENSUBDIV_ROOT}/include"
if [[ ! -f "${include_dir}/opensubdiv/far/topologyDescriptor.h" ]]; then
    emit_skip "OpenSubdiv headers were not found"
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
    emit_skip "OpenSubdiv libosdCPU was not found"
    [[ "${require_opensubdiv}" -eq 0 ]] || exit 2
    exit 0
fi

if ! command -v gsl-config >/dev/null 2>&1; then
    echo "gsl-config is required to compile the cache prototype." >&2
    exit 3
fi

tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/slimed-opensubdiv-cache-proof.XXXXXX")"
trap 'rm -rf "${tmp_dir}"' EXIT

repo_sources=()
while IFS= read -r source; do
    repo_sources+=("${source}")
done < <(find src -name '*.cpp' \
    ! -name 'Run_flat.cpp' \
    ! -name 'Run_dynamics_flat.cpp' \
    | sort)

cxx="${CXX:-c++}"
binary="${tmp_dir}/opensubdiv_regular_cache_prototype"
command=("${cxx}" -std=c++17 -DUSE_OPENSUBDIV_REGULAR -I include)
for flag in $(gsl-config --cflags); do
    command+=("${flag}")
done
if [[ -n "${OPENSUBDIV_CXXFLAGS:-}" ]]; then
    # shellcheck disable=SC2206
    extra_cxxflags=(${OPENSUBDIV_CXXFLAGS})
    command+=("${extra_cxxflags[@]}")
fi
command+=(
    experiments/opensubdiv_regular_cache_prototype.cpp
    "${repo_sources[@]}"
    -I "${include_dir}"
    -L "${lib_dir}"
    "-Wl,-rpath,${lib_dir}"
)
if [[ -n "${OPENSUBDIV_LDFLAGS:-}" ]]; then
    # shellcheck disable=SC2206
    extra_ldflags=(${OPENSUBDIV_LDFLAGS})
    command+=("${extra_ldflags[@]}")
fi
command+=(-losdCPU)
for flag in $(gsl-config --libs); do
    command+=("${flag}")
done
command+=(-pthread -o "${binary}")

"${command[@]}"
"${binary}"
