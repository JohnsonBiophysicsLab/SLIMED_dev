#!/usr/bin/env bash
set -euo pipefail

exec python3 "$(dirname "$0")/run_irregular_valence3_opensubdiv_face_loop.py" "$@"
