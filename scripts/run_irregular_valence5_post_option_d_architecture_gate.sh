#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 \
  "$ROOT/scripts/run_irregular_valence5_post_option_d_architecture_gate.py" \
  "$@"
