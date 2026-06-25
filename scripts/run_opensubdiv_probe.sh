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

if [[ -z "${OPENSUBDIV_ROOT:-}" ]]; then
    if [[ "${want_json}" -eq 1 ]]; then
        printf '{\n'
        printf '  "next_step": "Set OPENSUBDIV_ROOT to an OpenSubdiv install prefix and rerun.",\n'
        printf '  "reason": "OPENSUBDIV_ROOT is not set; OpenSubdiv probes are explicit opt-in only.",\n'
        printf '  "status": "skipped"\n'
        printf '}\n'
    else
        echo "status: skipped"
        echo "reason: OPENSUBDIV_ROOT is not set; OpenSubdiv probes are explicit opt-in only."
        echo "next_step: Set OPENSUBDIV_ROOT to an OpenSubdiv install prefix and rerun."
    fi
    if [[ "${require_opensubdiv}" -eq 1 ]]; then
        exit 2
    fi
    exit 0
fi

exec python3 scripts/probe_opensubdiv_feasibility.py \
    --opensubdiv-root "${OPENSUBDIV_ROOT}" \
    "$@"
