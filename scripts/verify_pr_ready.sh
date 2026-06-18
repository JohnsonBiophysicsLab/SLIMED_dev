#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STARTED_AT="$(date '+%Y-%m-%d %H:%M:%S %Z')"
CURRENT_STEP="startup"
COMPLETED_STEPS=()
VERIFY_DIR=""
VERIFY_REPO_DIR=""

cd "${ROOT_DIR}"

summarize() {
    local exit_code=$?

    if [[ -n "${VERIFY_DIR}" && -d "${VERIFY_DIR}" ]]; then
        rm -rf "${VERIFY_DIR}" || true
    fi

    echo
    if [[ ${exit_code} -eq 0 ]]; then
        echo "SLIMED PR verification: PASS"
    else
        echo "SLIMED PR verification: FAIL"
        echo "Failed step: ${CURRENT_STEP}"
    fi
    echo "Started: ${STARTED_AT}"
    echo "Repository: ${ROOT_DIR}"
    if [[ -n "${VERIFY_REPO_DIR}" ]]; then
        echo "Build/test copy: ${VERIFY_REPO_DIR} (removed)"
    fi
    echo "Completed steps: ${#COMPLETED_STEPS[@]}"
    if [[ ${#COMPLETED_STEPS[@]} -gt 0 ]]; then
        printf ' - %s\n' "${COMPLETED_STEPS[@]}"
    fi
}

trap summarize EXIT

run_step() {
    local label=$1
    shift

    CURRENT_STEP="${label}"
    echo
    echo "==> ${label}"
    "$@"
    COMPLETED_STEPS+=("${label}")
}

run_git_status() {
    local status_output

    CURRENT_STEP="git status --short"
    echo
    echo "==> ${CURRENT_STEP}"
    status_output="$(git status --short)"
    if [[ -n "${status_output}" ]]; then
        printf '%s\n' "${status_output}"
        echo "Working tree has local changes; continuing with build/test checks."
    else
        echo "(clean)"
    fi
    COMPLETED_STEPS+=("${CURRENT_STEP}")
}

prepare_verification_copy() {
    CURRENT_STEP="prepare temporary verification copy"
    echo
    echo "==> ${CURRENT_STEP}"

    VERIFY_DIR="$(mktemp -d "${TMPDIR:-/tmp}/slimed-pr-ready.XXXXXX")"
    VERIFY_REPO_DIR="${VERIFY_DIR}/repo"
    mkdir -p "${VERIFY_REPO_DIR}"
    cp -R "${ROOT_DIR}/." "${VERIFY_REPO_DIR}/"
    cd "${VERIFY_REPO_DIR}"

    echo "Using temporary copy: ${VERIFY_REPO_DIR}"
    COMPLETED_STEPS+=("${CURRENT_STEP}")
}

run_clean_build() {
    local target=$1

    run_step "make clean (before make ${target})" make clean
    run_step "make ${target}" make "${target}"
}

echo "SLIMED PR-ready verification"
echo "Builds run in a temporary copy; the current checkout is not cleaned."
echo "Required C++ standard: C++17."

run_git_status
prepare_verification_copy
run_clean_build serial
run_clean_build omp
run_clean_build dyna
run_clean_build dyna_omp
run_clean_build test
run_step "./bin/test_main" ./bin/test_main
