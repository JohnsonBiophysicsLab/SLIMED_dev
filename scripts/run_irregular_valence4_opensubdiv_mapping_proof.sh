#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

exec scripts/run_opensubdiv_probe.sh \
    --valence4-mapping-sample-transpose-report \
    "$@"
