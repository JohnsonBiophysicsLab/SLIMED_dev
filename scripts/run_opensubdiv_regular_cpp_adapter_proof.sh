#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

want_json=0
require_opensubdiv=0
for arg in "$@"; do
    if [[ "${arg}" == "--json" || "${arg}" == "--mode" ]]; then
        want_json=1
    fi
    if [[ "${arg}" == "--require-opensubdiv" ]]; then
        require_opensubdiv=1
    fi
done

emit_skip() {
    local reason=$1
    local next_step=$2
    if [[ "${want_json}" -eq 1 ]]; then
        printf '{\n'
        printf '  "next_step": "%s",\n' "${next_step}"
        printf '  "reason": "%s",\n' "${reason}"
        printf '  "status": "skipped"\n'
        printf '}\n'
    else
        echo "status: skipped"
        echo "reason: ${reason}"
        echo "next_step: ${next_step}"
    fi
}

if [[ -z "${OPENSUBDIV_ROOT:-}" ]]; then
    emit_skip \
        "OPENSUBDIV_ROOT is not set; the experimental C++ adapter proof is explicit opt-in only." \
        "Set OPENSUBDIV_ROOT to an OpenSubdiv install prefix and rerun."
    if [[ "${require_opensubdiv}" -eq 1 ]]; then
        exit 2
    fi
    exit 0
fi

include_dir="${OPENSUBDIV_ROOT}/include"
if [[ ! -f "${include_dir}/opensubdiv/far/topologyDescriptor.h" ]]; then
    emit_skip \
        "OpenSubdiv headers were not found under OPENSUBDIV_ROOT/include." \
        "Point OPENSUBDIV_ROOT at an install prefix containing include/opensubdiv."
    if [[ "${require_opensubdiv}" -eq 1 ]]; then
        exit 2
    fi
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
    emit_skip \
        "OpenSubdiv libosdCPU was not found under OPENSUBDIV_ROOT/lib or lib64." \
        "Point OPENSUBDIV_ROOT at an install prefix containing lib/libosdCPU."
    if [[ "${require_opensubdiv}" -eq 1 ]]; then
        exit 2
    fi
    exit 0
fi

tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/slimed-opensubdiv-cpp-proof.XXXXXX")"
cleanup() {
    rm -rf "${tmp_dir}"
}
trap cleanup EXIT

cxx="${CXX:-c++}"
binary="${tmp_dir}/opensubdiv_regular_cpp_adapter_proof"
command=(
    "${cxx}"
    -std=c++17
)
if [[ -n "${OPENSUBDIV_CXXFLAGS:-}" ]]; then
    # shellcheck disable=SC2206
    extra_cxxflags=(${OPENSUBDIV_CXXFLAGS})
    command+=("${extra_cxxflags[@]}")
fi
command+=(
    experiments/opensubdiv_regular_cpp_adapter_proof.cpp
    -I "${include_dir}"
    -L "${lib_dir}"
    "-Wl,-rpath,${lib_dir}"
)
if [[ -n "${OPENSUBDIV_LDFLAGS:-}" ]]; then
    # shellcheck disable=SC2206
    extra_ldflags=(${OPENSUBDIV_LDFLAGS})
    command+=("${extra_ldflags[@]}")
fi
command+=(
    -losdCPU
    -o "${binary}"
)

"${command[@]}"
"${binary}"
