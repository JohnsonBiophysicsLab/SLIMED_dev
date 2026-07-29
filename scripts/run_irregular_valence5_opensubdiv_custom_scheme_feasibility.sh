#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 \
  "${SCRIPT_DIR}/run_irregular_valence5_opensubdiv_custom_scheme_feasibility.py" \
  "$@"
