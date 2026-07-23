#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

exec python3 scripts/run_irregular_valence4_opensubdiv_force_formula_proof.py "$@"
