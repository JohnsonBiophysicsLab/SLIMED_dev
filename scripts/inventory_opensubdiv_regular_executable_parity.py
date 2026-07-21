#!/usr/bin/env python3

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "src/mesh/OpenSubdiv_regular_evaluator.cpp": (
        "SLIMED_OPENSUBDIV_REGULAR_EXECUTABLE_PARITY",
        "constexpr bool kOpenSubdivRegularProductionRouteEnabled = false",
    ),
    "experiments/opensubdiv_regular_executable_parity.cpp": (
        "candidate_rows_installed_in_diagnostic_build",
        "not_production_routing",
        "global_energy",
        "vertex_forces",
        "face_normals",
        "face_legacy_volume",
    ),
    "scripts/run_opensubdiv_regular_executable_parity.sh": (
        "-DSLIMED_OPENSUBDIV_REGULAR_EXECUTABLE_PARITY",
        "OMP_NUM_THREADS",
        "env -u SLIMED_USE_OPENSUBDIV_REGULAR",
    ),
    "scripts/compare_opensubdiv_regular_executable_parity.py": (
        "disabled_double_row_serial_openmp_executable_output_parity",
        "route_activation_allowed",
        "candidate_serial_vs_openmp",
    ),
}


def inspect():
    missing = []
    for relative, anchors in EXPECTED.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        for anchor in anchors:
            if anchor not in text:
                missing.append(f"{relative}: {anchor}")
    macro_leaks = []
    for base in ("include", "EXEs", ".github", "Makefile"):
        path = ROOT / base
        candidates = [path] if path.is_file() else path.rglob("*")
        for candidate in candidates:
            if not candidate.is_file():
                continue
            try:
                text = candidate.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if "SLIMED_OPENSUBDIV_REGULAR_EXECUTABLE_PARITY" in text:
                macro_leaks.append(str(candidate.relative_to(ROOT)))
    return missing, sorted(macro_leaks)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    missing, macro_leaks = inspect()
    print(f"anchors: {sum(len(value) for value in EXPECTED.values())}")
    print(f"missing: {len(missing)}")
    print(f"production_macro_leaks: {len(macro_leaks)}")
    for item in missing + macro_leaks:
        print(item)
    return 1 if args.check and (missing or macro_leaks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
