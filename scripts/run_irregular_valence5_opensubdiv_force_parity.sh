#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "${ROOT_DIR}/scripts/run_irregular_valence5_opensubdiv_force_parity.py" "$@"
