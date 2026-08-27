#!/usr/bin/env python3
"""Fail-closed inventory for the unified irregular Loop architecture ADR.

This script is deliberately read-only. It describes current main separately
from the unmerged PR 176 production root and PR 182 evidence leaf, and rejects
source, fixture, policy, or ADR drift before later work packages rely on the
baseline.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
import os
import re
import struct
import subprocess
import sys
import tokenize
from fractions import Fraction
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
# Immutable historical range for the reviewed WP0 ownership audit. Package
# linearity is deliberately measured from MAINLINE_REF instead.
BASE_SHA = "e9af3ddad494fc073040ee82bdf07944b9fee8cf"
ORIGINAL_WP01_BASE_SHA = "906a7850d2c1ceec3ffdda9bf0ce44a437f6aa4a"
WP0_REVIEWED_ENDPOINT_SHA = "f8e76ea5bb444ba447a5ae9178a309545f2533ba"
PR176_SHA = "46c06080fb663bcb43f38cf32fc1b45daa8732e8"
PR182_SHA = "9587e3dce4509029e611e2937bac570b410193c3"
PR182_MERGE_BASE = "6d9213e260c90c74c72e831deab1a2ec2d67e1d3"
MAINLINE_REF = "origin/main"

EXPECTED_BUILD_FLAGS = [
    "USE_OPENSUBDIV_REGULAR",
    "USE_OPENSUBDIV_VALENCE3",
    "USE_OPENSUBDIV_VALENCE5",
]
EXPECTED_RUNTIME_FLAGS = [
    "SLIMED_USE_OPENSUBDIV_REGULAR",
    "SLIMED_USE_OPENSUBDIV_VALENCE4",
    "SLIMED_USE_OPENSUBDIV_VALENCE5",
    "SLIMED_USE_OPENSUBDIV_VALENCE5_PHASE2",
]
EXPECTED_VOLUME_FACTOR_NAMES = ["kLegacyVolumeQuadratureFactor"]
EXPECTED_VOLUME_FUNCTIONAL_TOKENS: list[str] = []
LEGACY_VOLUME_FACTOR_LITERAL = "0.16666666666"
EXPECTED_WP0_PATHS = [
    "docs/adr_unified_loop_backend.md",
    "docs/irregular_loop_architecture_reassessment.md",
    "docs/unified_irregular_loop_implementation_plan.md",
    "scripts/inventory_unified_loop_baseline.py",
    "tests/test_unified_loop_baseline_inventory.py",
]
EXPECTED_VALENCE5_FACE_SOURCE_MAPPING_SHA256 = (
    "9f5fe4e76a9815a806970164d4a5e02771c4350a6c1047ceb7ce3e86cd2acd1a")

EXPECTED_FACES = {
    "valence3_tetrahedron": [
        [0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]
    ],
    "valence4_octahedron": [
        [0, 2, 3], [0, 3, 4], [0, 4, 5], [0, 5, 2],
        [1, 3, 2], [1, 4, 3], [1, 5, 4], [1, 2, 5],
    ],
    "valence5_icosahedron": [
        [0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11],
        [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8],
        [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9],
        [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1],
    ],
}

EXPECTED_FIXTURE_HASHES = {
    "data/fixtures/candidates/closed_valence3_tetrahedron/candidate_metadata.json":
        "3b2cf28dd5b4b52ea5a999e07fc89527513066ac8f2ef20b52137448fcb52660",
    "data/fixtures/candidates/closed_valence3_tetrahedron/faces.csv":
        "acfbd18a1922e465052f6badf5aa2567faa282add3edc7867f3bca7493e6e1aa",
    "data/fixtures/candidates/closed_valence3_tetrahedron/vertices.csv":
        "4a82e312830953d67731970042f5cf7d174e6af9f8844b7cd2b321209e51b898",
    "data/fixtures/candidates/closed_valence4_octahedron/candidate_metadata.json":
        "2109779d724d924ac416a127fa4a376cf1a72fbe9fa1391223995ebbccb60b74",
    "data/fixtures/candidates/closed_valence4_octahedron/faces.csv":
        "af9742137b89c25cc29e8b60e137967d8adfcdd80f33d3172fc13f1ed93838e8",
    "data/fixtures/candidates/closed_valence4_octahedron/vertices.csv":
        "b650ff4c1aed263701d25305d846f520933a2deb457655558f17a855e65c88b7",
    "data/fixtures/candidates/closed_mixed_valence345/candidate_metadata.json":
        "74ae00951e6ea20021722a45a887d0c47530d4d7248cb69f553cb1a66a60f14b",
    "data/fixtures/candidates/closed_mixed_valence345/faces.csv":
        "bc1db1bf7fb29e4e4bc7b41f93ea9c206fe80a022736f1f02d22063c0b800233",
    "data/fixtures/candidates/closed_mixed_valence345/vertices.csv":
        "affa93eec68b8de9d5dcd12d31bf1d7222410722b0cca44c58495c558e3d7287",
    "data/fixtures/closed_valence5/faces.csv":
        "561b3ec0c4aa6b1e684ef87c2738d8c20a474225bd4960a4a672d306a3e70327",
    "data/fixtures/closed_valence5/vertices.csv":
        "d0dae733433503f9e2aba4f8eda80fa2d6842d0f5a7b922d7ffce158f505cb45",
}

EXPECTED_B2P_FIXTURE_HASHES = {
    "data/fixtures/candidates/b2p_single_flip_family/base/candidate_metadata.json":
        "66c9ab55624afb0f7fc8b444e6e5d9479bde356483bb11a73e0d5c6ce3edd35d",
    "data/fixtures/candidates/b2p_single_flip_family/base/faces.csv":
        "bcc295b8c7e972982676afedb7ead94bbddfd4702f6d638a070630c9f32f7672",
    "data/fixtures/candidates/b2p_single_flip_family/base/vertices.csv":
        "b538595170eca52b4b648cbc3c91e6f63ff6b0a40fc16a6f2a786d5b464c4f52",
    "data/fixtures/candidates/b2p_single_flip_family/family_metadata.json":
        "c8ac7ea89681b72508a29b2bca8f8b97ef2c65acab6aebe19445ae8eb7136fa2",
    "data/fixtures/candidates/b2p_single_flip_family/flip_000/candidate_metadata.json":
        "226312a46cb6f611efa54866b37787a01b68aa783d614936982b407bf0dc55d9",
    "data/fixtures/candidates/b2p_single_flip_family/flip_000/faces.csv":
        "744b5a91acbdf6926890eb378dd7410a580155bd84ffb583c49d63a6a56fca76",
    "data/fixtures/candidates/b2p_single_flip_family/flip_000/vertices.csv":
        "b538595170eca52b4b648cbc3c91e6f63ff6b0a40fc16a6f2a786d5b464c4f52",
    "data/fixtures/candidates/b2p_single_flip_family/flip_001/candidate_metadata.json":
        "b0315a513777cad7fb5f5ba9eed395959e3bce6848283c07cf7d7f0fccde974e",
    "data/fixtures/candidates/b2p_single_flip_family/flip_001/faces.csv":
        "58d78e761bcfb8172eff55084ad99968c14089ba08b2af78f3504ba621c9bc74",
    "data/fixtures/candidates/b2p_single_flip_family/flip_001/vertices.csv":
        "b538595170eca52b4b648cbc3c91e6f63ff6b0a40fc16a6f2a786d5b464c4f52",
    "data/fixtures/candidates/b2p_single_flip_family/flip_002/candidate_metadata.json":
        "a66f2872f64ca861ca6648118aa4981482fc5f247742c5c189ecc906288f934e",
    "data/fixtures/candidates/b2p_single_flip_family/flip_002/faces.csv":
        "7ee844bfaec6aad97892673d63c7a00522e141db3dc707b6615be6852fd83727",
    "data/fixtures/candidates/b2p_single_flip_family/flip_002/vertices.csv":
        "b538595170eca52b4b648cbc3c91e6f63ff6b0a40fc16a6f2a786d5b464c4f52",
    "data/fixtures/candidates/b2p_valence789/candidate_metadata.json":
        "f6a88b98adec1a90f4d591b9711aa20fd724b14755beadf064e42af8328a381b",
    "data/fixtures/candidates/b2p_valence789/faces.csv":
        "bcc295b8c7e972982676afedb7ead94bbddfd4702f6d638a070630c9f32f7672",
    "data/fixtures/candidates/b2p_valence789/vertices.csv":
        "b538595170eca52b4b648cbc3c91e6f63ff6b0a40fc16a6f2a786d5b464c4f52",
    "data/fixtures/candidates/b2p_adjacent_extraordinary/candidate_metadata.json":
        "de6bf74052e24f26049c3d194570a081d47bd5dcd278ad9b34c6b1cf39973d1b",
    "data/fixtures/candidates/b2p_adjacent_extraordinary/faces.csv":
        "1ecbe26328311f99b2e55ccdc7e1d614947099fe1fff124cfca83dc62f5dddbb",
    "data/fixtures/candidates/b2p_adjacent_extraordinary/vertices.csv":
        "b650ff4c1aed263701d25305d846f520933a2deb457655558f17a855e65c88b7",
}

EXPECTED_B2P_TARGETS = {
    "irregular_position_row_accuracy": 5.0e-6,
    "irregular_first_derivative_row_accuracy": 2.5e-5,
    "irregular_second_derivative_row_accuracy": 1.25e-4,
    "flip_pair_row_changed_linf": 1.0e-12,
}

EXPECTED_B2_READINESS_FIXTURE_HASHES = {
    "data/fixtures/candidates/b2_readiness_v1/asymmetric_344_bipyramid/candidate_metadata.json":
        "e92b244806eaecd9230a3f3f9977f61ddeff3875ee6550c2dfbdb211a8e05e04",
    "data/fixtures/candidates/b2_readiness_v1/asymmetric_344_bipyramid/faces.csv":
        "c621d95a16a6915ab443bf74f162bddde96a85ee82e06152cbef82f28ef87486",
    "data/fixtures/candidates/b2_readiness_v1/asymmetric_344_bipyramid/vertices.csv":
        "b275aac1d1b422a131c3703eb7f56fd4d5bf21230b277835774bc27405d10a4e",
    "data/fixtures/candidates/b2_readiness_v1/closed_566_refined_icosahedron/candidate_metadata.json":
        "f974fb5bb1d542561672c1e7d2d52bf5220acc09dd3b5510dc14f1d98343b0b5",
    "data/fixtures/candidates/b2_readiness_v1/closed_566_refined_icosahedron/faces.csv":
        "d72e02a882c536643e8a3405efe8bb32c745bc034cbc55dcc1af0d5eba11e1b8",
    "data/fixtures/candidates/b2_readiness_v1/closed_566_refined_icosahedron/vertices.csv":
        "cb6c618c254b36bbe27ff354f5dc009222e95277188833a3385a4f3c378b0bd6",
    "data/fixtures/candidates/b2_readiness_v1/execution_manifest.json":
        "bdadac60281c0430789e079cefb819c0c8e127899d4ede4ba7227d233452a07b",
    "data/fixtures/candidates/b2_readiness_v1/regular_all6_torus/candidate_metadata.json":
        "11aba5339fced78cab1056b99d03766ecf3b0a7178e1c04c5376f1af01f2cf1c",
    "data/fixtures/candidates/b2_readiness_v1/regular_all6_torus/faces.csv":
        "7797a1ded38d99e83707fb85e23a2a193c5857f7425a5f678ceccb1506c67cd0",
    "data/fixtures/candidates/b2_readiness_v1/regular_all6_torus/vertices.csv":
        "923914e925eaf0f60eb9a087f0150ad37b9e56bf0191ffc52b5d7fbd91b2903c",
    "data/fixtures/candidates/b2_readiness_v1/symmetric_344_bipyramid/candidate_metadata.json":
        "6afd2ec0c0df1cd71a8597fa78889dbf9daea9627d10b97165acec1cd39f9cb0",
    "data/fixtures/candidates/b2_readiness_v1/symmetric_344_bipyramid/faces.csv":
        "c621d95a16a6915ab443bf74f162bddde96a85ee82e06152cbef82f28ef87486",
    "data/fixtures/candidates/b2_readiness_v1/symmetric_344_bipyramid/vertices.csv":
        "bbce1680eb4006622e14dd5d724134df826471bb55e0332c19a208b5e92429a5",
}

EXPECTED_B2_READINESS_CRITERIA = {
    "b2_preparation_median_ms": 1000.000,
    "b2_preparation_single_run_failstop_ms": 10000.000,
    "b2_retained_row_payload_bytes_per_face": 131072.0,
    "b2_preparation_peak_rss_delta_mib": 64.000,
}

EXPECTED_B2_READINESS_MANIFEST_CONTRACT_SHA256 = (
    "30db9a564c165c2f04125f25a983df6301225ca4355386bf5c91a500ea67f368")
EXPECTED_B2_READINESS_GENERATOR_SHA256 = (
    "7a2232133184ac2689159629b77e4971728d18df52d0b8ddafd3ac6e3594ccb2")
EXPECTED_B2_READINESS_SOURCE_ROW_IDS = [
    *[f"U8-{index:02d}" for index in range(1, 15)],
    "B7-01", "B7-02", "B7-03",
]
EXPECTED_B2_READINESS_EXECUTION_CASE_IDS = [
    "u8_01_regular_closed", "u8_02_tetrahedron", "u8_03_octahedron",
    "u8_04_icosahedron", "u8_05_symmetric_344", "u8_06_asymmetric_344",
    "u8_07_mixed_345", "u8_08_closed_566", "u8_09_nonplatonic",
    "u8_10_coordinate_perturbed", "u8_11_reversed_winding",
    "u8_12_open_boundary", "u8_13_duplicate_face",
    "u8_14_edge_flip_family", "b7_01_single_flip_family",
    "b7_02_valence789", "b7_03_adjacent_extraordinary",
]
EXPECTED_B2_READINESS_ALIAS_PAIRS = [
    ["b7_01_single_flip_family", "u8_14_edge_flip_family"],
    ["b7_02_valence789", "u8_09_nonplatonic"],
]
EXPECTED_B2_READINESS_UNIQUE_CONTENT_IDENTITIES = [
    "regular_all6_torus", "closed_valence3_tetrahedron",
    "closed_valence4_octahedron", "closed_valence5",
    "symmetric_344_bipyramid", "asymmetric_344_bipyramid",
    "closed_mixed_valence345", "closed_566_refined_icosahedron",
    "b2p_shared_hull_base", "asymmetric_344_binary64_perturbed",
    "invalid_reversed_face_zero", "invalid_deleted_face_zero",
    "invalid_appended_face_zero", "b2p_flip_000", "b2p_flip_001",
    "b2p_flip_002", "b2p_adjacent_extraordinary",
]
EXPECTED_B2_READINESS_VALID_THREAD_CONTENT_IDENTITIES = [
    value for value in EXPECTED_B2_READINESS_UNIQUE_CONTENT_IDENTITIES
    if not value.startswith("invalid_")
]
EXPECTED_B2_READINESS_SAMPLE_POLICY_IDS = [
    "regular_interior_l6_10", "extraordinary_trend_24_per_corner",
    "full_surface_plus_extraordinary_trend",
    "full_surface_extraordinary_flip_locality", "none_rejection",
]

EXPECTED_B2_READINESS_ANCHORS = [
    "`30db9a564c165c2f04125f25a983df6301225ca4355386bf5c91a500ea67f368`",
    "3 unrecorded warmups followed by 15 measured\npreparations",
    "ordinary\nmedian is the eighth sorted value",
    "Bfr\n`approxLevelSmooth = 2,3,4,5,6,7,8` with `approxLevelSharp = 6`",
    "Far\nisolation level `2,3,4,5,6,7,8`",
    "`hw.model=Mac17,2`",
    "`hw.memsize=25769803776`",
    "`Apple clang version 21.0.0 (clang-2100.1.1.101)`",
    "`mach_continuous_time` converted with `mach_timebase_info`",
    "`IOPSCopyPowerSourcesInfo` plus `IOPSGetProvidingPowerSourceType`",
    "`NSProcessInfo.thermalState`",
    "`UNQUALIFIED_PLATFORM`",
    "`UNSUPPORTED/BLOCKING`",
    "one shared immutable full-mesh `Far::TopologyRefiner`",
    "Per-worker results are destroyed after comparison while shared\nstate persists through all 20 rounds",
    "Far has one proof-only uncached\nconstruction mode, recorded as cache mode `not_applicable`",
    "The TSan build below is a separate\ncategorical threading profile",
    "The only library target is `osd_static_cpu`",
    "ordered 47-translation-unit expansion",
    "`compile_commands.json`",
    "`BUILD_PROVENANCE_FAILURE`",
    "12 + 4*U + 72*S + 12*C",
    "changes no D10 value or oracle input",
]

FORBIDDEN_B2_READINESS_CLAIM_TOKENS = [
    "bfr_" + "qualified",
    "far_" + "qualified",
    "candidate_" + "comparison_result",
    '"d9a_decision": "pass"',
    '"qualification_claim": "pass"',
]

EXPECTED_B2P_ORACLE_ANCHORS = [
    "repository-owned `MpfrInterval`",
    "`mpfr_init2(...,544)`",
    "exactly MPFR 4.2.2",
    "MPFR_RNDD",
    "MPFR_RNDU",
    "mpfr_const_pi",
    "scalar Boost MPFR wrapper is not an interval implementation",
    "1.0e-70",
    "kappa_infinity(V) = ||V||_infinity * ||V^-1||_infinity",
    "smallest source ID is the pivot",
    "spectral projector",
    "d = d0,d0+1,...,d0+4",
    "d0+4 <= 30",
    "intersect its five outward-rounded coefficient",
    "required exact binary64 import of `d_i`",
    "required exact binary64 import of `c_i`",
    "epsilon_i = max(abs(d_i - lo_i), abs(hi_i - d_i))",
    "E_coeff = sum_i epsilon_i",
    "E_a = sum_i ([lo_i,hi_i] - d_i) * P_i[a]",
    "E_geom = max_a(max(abs(lower(E_a)), abs(upper(E_a))) / lower(L_M))",
    "exactly reimported before `E_coeff` and `E_geom` are evaluated",
    "u_i = max(abs(c_i - lo_i), abs(c_i - hi_i))",
    "U_coeff = sum_i u_i",
    "D_a = sum_i ([lo_i,hi_i] - c_i) * P_i[a]",
    "U_geom = max_a(max(abs(lower(D_a)), abs(upper(D_a))) / lower(L_M))",
    "Pointwise midpoint differences are diagnostic only",
    "is a candidate FAIL and may never be relabeled oracle-uncovered",
    "lower(L_M)",
    "exact singleton",
    "0/0",
    "Loop refinement identity",
    "mandatory primary computation is Stam eigenanalysis",
    "S^d = V*Lambda^d*V^-1",
    "interval Krawczyk inclusion",
    "uniform success cannot supply coverage when the primary route fails",
    "q_Bfr = q_Far = q",
    "J0 = [[ 1, 0],[ 0, 1]]",
    "J1 = [[ 0, 1],[-1,-1]]",
    "J2 = [[-1,-1],[ 1, 0]]",
    "G_q = G_y * B",
    "H_q = transpose(B) * H_y * B",
    "r < 2^-8",
    "r = 2^-1, 2^-2, ..., 2^-8",
    "depths 0 through 12",
    "uniform subdivider applies the stock even/odd Loop masks",
    "1.0e-20",
]

EXPECTED_B2P_EXECUTION_AND_EVIDENCE_ANCHORS = [
    "`.github/workflows/bfr_qualification.yml`",
    "explicit `MPFR_ROOT` and `OPENSUBDIV_ROOT` values",
    "`-lmpfr -lgmp`",
    "`--require-proof-dependencies` mode exits nonzero",
    "not allowed to report `skipped`",
    "must not count the two directory names as independent mesh-level",
    "therefore no valence-6 vertex at depth zero",
    "frozen negative-evidence risk to accept explicitly with D10",
]

EXPECTED_B2P_LOCALITY_SAMPLE_MANIFEST = {
    "applicability": "every comparable unchanged face in every listed variant",
    "coordinate_rule": (
        "Use the same oriented face-local (u,v) coordinate in base and member; "
        "do not permute corners and do not duplicate samples per corner."
    ),
    "lattice_denominator": 6,
    "order_rule": (
        "Increasing i+j from 2 through 5, then increasing i; j=(i+j)-i."
    ),
    "row_order": ["position", "du", "dv", "duu", "duv", "dvv"],
    "samples": [
        {
            "barycentric_numerators": [6 - i - j, i, j],
            "id": f"tri-l6-s{i + j:02d}-u{i:02d}-v{j:02d}",
            "u_numerator": i,
            "v_numerator": j,
        }
        for total in range(2, 6)
        for i in range(1, total)
        for j in (total - i,)
    ],
}

FORBIDDEN_B2P_CLAIM_TOKENS = [
    "candidate_" + "comparison_result",
    "bfr_" + "qual" + "ified",
    "far_" + "is_more_accurate",
    "bfr_" + "is_more_accurate",
]

EXPECTED_DECISIONS = {
    "D0": "Proposed - pending explicit user stack disposition",
    "D1": "Approved - Stock OpenSubdiv 3.7.0 Loop semantics are the forward-looking CPU proof baseline. Completed rows are not modified to reproduce legacy masks. This does not select Far versus Bfr, does not change the production default, and does not approve arbitrary production inputs.",
    "D2": "Approved - The initial generic proof scope is complete, closed, consistently oriented, two-manifold triangular meshes. Boundaries, holes, ghosts, non-triangles, non-manifold incidence, and inconsistent orientation must fail before mutation. This does not decide D2b and does not authorize production activation.",
    "D2b": "Proposed - pending explicit user production-scope approval",
    "D3": "Pending post-WP2.1 oracle, independent scientific review, and user decision",
    "D4": "Pending post-WP2.1 characterization, independent scientific review, and user decision",
    "D5": "Pending WP1.1a evidence and explicit user approval",
    "D6": "Restated existing project policy",
    "D7": "Restated existing user instruction",
    "D8": "Proposed - pending explicit user performance-budget approval",
    "D12": "Approved - B2 readiness criteria, schema-2 execution manifest, fixture corpus, and exact qualification/build protocol are frozen for B2. This does not qualify Bfr, decide D9a/D9b or D8, or authorize production.",
}

EXPECTED_PLAN_AUTHORITIES = {
    "D0": "Explicit user decision",
    "D1": "Explicit user scientific decision, informed by prior Valence-5 acceptance",
    "D2": "Explicit user decision",
    "D2b": "Explicit user production-scope decision",
    "D3": "WP2.1 oracle, independent scientific review, and explicit user scientific decision",
    "D4": "WP2.1 characterization, independent scientific review, and explicit user decision",
    "D5": "Explicit user decision after WP1.1a; any `5/6/6` implementation needs a separate scientific gate",
    "D6": "Existing project policy",
    "D7": "Existing user instruction",
    "D8": "Reproduced benchmark evidence plus explicit user approval",
}

EXPECTED_PERFORMANCE_BUDGET = {
    "generic_vs_cached_regular_median": "TBD",
    "generic_vs_direct_regular_each_case": 2.00,
}
EXPECTED_D8_PENDING_ANCHOR_COUNTS = {
    "docs/adr_unified_loop_backend.md": 2,
    "docs/unified_irregular_loop_implementation_plan.md": 2,
}
EXPECTED_D8_DIRECT_ANCHOR_COUNTS = {
    "docs/adr_unified_loop_backend.md": 2,
    "docs/unified_irregular_loop_implementation_plan.md": 2,
}

EXPECTED_ENERGY_FIELDS = [
    "energyCurvature", "energyArea", "energyVolume", "energyThickness",
    "energyTilt", "energyRegularization", "energyHarmonicBond",
    "energyGagScaffolding", "energyIdealizedProteinLattice", "energyTotal",
]

EXPECTED_TOLERANCES = {
    "regular_row_and_route_parity": {
        "value": 5.0e-6,
        "source": "src/mesh/OpenSubdiv_regular_evaluator.cpp",
        "owner": "existing regular OpenSubdiv proof/route",
    },
    "regular_residual_scale_floor": {
        "value": 1.0e-12,
        "source": "src/mesh/OpenSubdiv_regular_evaluator.cpp",
        "owner": "existing regular OpenSubdiv residual metric",
    },
    "valence3_row_invariants": {
        "value": 1.0e-12,
        "source": "src/mesh/OpenSubdiv_valence3_row_provider.cpp",
        "owner": "existing Valence-3 proof provider",
    },
    "valence4_row_invariants": {
        "value": 1.0e-12,
        "source": "src/mesh/OpenSubdiv_valence4_row_provider.cpp",
        "owner": "existing Valence-4 exact route",
    },
    "valence5_row_invariants": {
        "value": 1.0e-12,
        "source": "src/mesh/OpenSubdiv_valence5_row_provider.cpp",
        "owner": "existing Valence-5 exact route",
    },
    "valence5_reviewed_production_parity": {
        "value": 1.0e-10,
        "source": "include/energy_force/Valence5_opensubdiv_face_loop.hpp",
        "owner": "existing Valence-5 Phase-3 activation",
    },
    "irregular_serial_openmp_envelope": {
        "value": 1.0e-10,
        "source": "docs/irregular_serial_omp_tolerance_characterization.md",
        "owner": "existing irregular reduction characterization",
    },
}


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _sha256(relative: str) -> str:
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def _csv_int_rows(relative: str) -> list[list[int]]:
    with (ROOT / relative).open(newline="", encoding="utf-8") as stream:
        return [[int(value) for value in row] for row in csv.reader(stream)]


def _source_corpus() -> str:
    chunks: list[str] = []
    for base in (ROOT / "src", ROOT / "include"):
        for path in sorted(base.rglob("*")):
            if path.suffix in {".cpp", ".cu", ".cuh", ".hpp", ".h"}:
                chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def _initializer_rows(text: str, marker: str, columns: int) -> list[list[int]]:
    start = text.index(marker)
    block = text[start:text.index("}};", start) + 3]
    number = r"(-?\d+)"
    pattern = r"\{\{\s*" + r"\s*,\s*".join([number] * columns) + r"\s*\}\}"
    return [[int(value) for value in match]
            for match in re.findall(pattern, block)]


def _rows_sha256(rows: list[list[int]]) -> str:
    encoded = json.dumps(rows, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _all_present(text: str, anchors: list[str]) -> bool:
    return all(anchor in text for anchor in anchors)


def _cpp_code(text: str) -> str:
    """Mask C++ comments and ordinary/raw literals, preserving positions."""
    text = re.sub(r"\\\r?\n", "", text)
    masked = list(text)
    index = 0
    state = "code"
    raw_start = re.compile(
        r"(?:u8|[uUL])?R\"([^\s()\\]{0,16})\(")
    while index < len(text):
        current = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if state == "code":
            raw = raw_start.match(text, index)
            if raw and (index == 0 or not (text[index - 1].isalnum() or
                                           text[index - 1] == "_")):
                closing = ")" + raw.group(1) + '"'
                end = text.find(closing, raw.end())
                end = len(text) if end < 0 else end + len(closing)
                for cursor in range(index, end):
                    if text[cursor] != "\n":
                        masked[cursor] = " "
                index = end
                continue
            if current == "/" and following == "/":
                masked[index] = masked[index + 1] = " "
                index += 2
                state = "line_comment"
                continue
            if current == "/" and following == "*":
                masked[index] = masked[index + 1] = " "
                index += 2
                state = "block_comment"
                continue
            if current in ('"', "'"):
                masked[index] = " "
                state = "string" if current == '"' else "character"
                index += 1
                continue
        elif state == "line_comment":
            if current == "\n":
                state = "code"
            else:
                masked[index] = " "
            index += 1
            continue
        elif state == "block_comment":
            if current == "*" and following == "/":
                masked[index] = masked[index + 1] = " "
                index += 2
                state = "code"
                continue
            if current != "\n":
                masked[index] = " "
            index += 1
            continue
        else:
            if current != "\n":
                masked[index] = " "
            if current == "\\" and following:
                if following != "\n":
                    masked[index + 1] = " "
                index += 2
                continue
            if ((state == "string" and current == '"') or
                    (state == "character" and current == "'")):
                state = "code"
            index += 1
            continue
        index += 1
    return "".join(masked)


_CPP_DIRECTIVE_PREFIX = r"(?:#|%:|\?\?=)"
_INCLUDE_GUARD_NAME = re.compile(r"[A-Z][A-Z0-9_]*_(?:H|HPP)")
_REVIEWED_MESH_HEADER_INCLUDES = (
    "<math.h>", "<cmath>", "<vector>", "<iostream>", "<fstream>",
    "<sstream>", "<string>", "<stdexcept>", "<array>", "<cstdint>",
    "<limits>", "<unordered_map>", "<omp.h>", "<algorithm>",
    '"mesh/Face.hpp"', '"mesh/Vertex.hpp"',
    '"energy_force/Energy.hpp"', '"energy_force/Force.hpp"',
    '"mesh/Gauss_quadrature.hpp"',
    '"mesh/Regular_limit_surface_row_cache.hpp"',
    '"mesh/Loop_topology_transaction.hpp"',
    '"linalg/Linear_algebra.hpp"', '"Parameters.hpp"',
)
_REVIEWED_IMPORT_INCLUDES = (
    '"mesh/Mesh.hpp"', '"mesh/Limit_surface_evaluator.hpp"',
    '"mesh/OpenSubdiv_regular_evaluator.hpp"', "<sstream>", "<stdexcept>",
)
_REVIEWED_FLAT_INCLUDES = ('"mesh/Mesh.hpp"',)
_REVIEWED_TRANSACTION_INCLUDES = (
    '"mesh/Loop_topology_transaction.hpp"', "<algorithm>", "<limits>",
    "<type_traits>", "<utility>", '"mesh/Mesh.hpp"',
)
_REVIEWED_TRANSACTION_COMMIT_SHA256 = (
    "19485b5963d97cd60472e5c66dcf5a275ad6b410fb32270beb7545cd8f4dc748")
_REVIEWED_IMPORT_SETUP_SHA256 = (
    "f4c489797126ea63ab7bbe1c7bfa054cef0bdd84e05e5a53f7579149d6d78d9a")
_REVIEWED_FLAT_SETUP_SHA256 = (
    "2a87b985a058db11429bb86c9ed49d186ed558eaf3a671fd08722e512e8586f4")
_REVIEWED_CHECKPOINT_WRITER_SHA256 = (
    "d0fcc2377f984854926cf35740cd0f62db9d70822d33317f8f95d697666b5446")
_REVIEWED_CHECKPOINT_INCLUDES = (
    ("include", '"io/io.hpp"'),
    ("include", "<algorithm>"),
    ("include", "<cstdio>"),
    ("include", "<iomanip>"),
)
_REVIEWED_CHECKPOINT_SOURCE_SURFACE_SHA256 = (
    "60fa90db08c25f5a3f81c7359ac6c91a5792be2452d038a6aaf8658c6a81eac0")
_REVIEWED_OTHER_SOURCE_COUNT = 86
_REVIEWED_OTHER_INCLUSION_SHA256 = (
    "8be98f909e50b3e463616d7b050705697a9f2baa730c2973673b166d86482817")


def _source_inclusion_directives(text: str) -> tuple[tuple[str, str], ...]:
    """Return logical-line include/import directives and their operands."""
    text = re.sub(r"\\\r?\n", "", text)
    code = _cpp_code(text)
    directives: list[tuple[str, str]] = []
    for match in re.finditer(
        rf"^\s*{_CPP_DIRECTIVE_PREFIX}\s*"
            r"(include|include_next|import)\b", code, re.MULTILINE):
        line_end = text.find("\n", match.end())
        line_end = len(text) if line_end < 0 else line_end
        directives.append((match.group(1), text[match.end():line_end].strip()))
    return tuple(directives)


def _source_inclusion_surface_sha256(sources: list[str]) -> str:
    surface = [_source_inclusion_directives(source) for source in sources]
    encoded = json.dumps(surface, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _only_reviewed_preprocessor_includes(
        text: str,
        reviewed: tuple[tuple[str, str], ...]) -> bool:
    """Require an exact include surface and reject every other directive."""
    code = _cpp_code(text)
    directives = tuple(match.group(1) for match in re.finditer(
        rf"^\s*{_CPP_DIRECTIVE_PREFIX}\s*([A-Za-z_]\w*)\b",
        code, re.MULTILINE))
    return (all(name == "include" for name in directives) and
            _source_inclusion_directives(text) == reviewed)


def _checkpoint_source_surface_sha256() -> str:
    """Hash production build membership and every compiled source/header."""
    suffixes = {
        ".cpp", ".cc", ".cxx", ".cu", ".mm",
        ".hpp", ".h", ".cuh", ".ipp", ".tpp", ".inl"}
    makefile = _text("Makefile")
    surface: list[tuple[str, str]] = [
        ("Makefile", hashlib.sha256(makefile.encode("utf-8")).hexdigest())]
    for base in (ROOT / "src", ROOT / "include", ROOT / "EXEs"):
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix not in suffixes:
                continue
            relative = path.relative_to(ROOT).as_posix()
            text = _text(relative)
            surface.append(
                (relative, hashlib.sha256(text.encode("utf-8")).hexdigest()))
    encoded = json.dumps(surface, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _make_override_environment_absent() -> bool:
    """Require a clean make/compiler override environment for inventory."""
    override_names = (
        "MAKEFILES", "MAKEFLAGS", "GNUMAKEFLAGS", "MFLAGS",
        "MAKEOVERRIDES", "CC", "CXX", "CPP", "AS", "LD", "AR",
        "RANLIB", "NM", "STRIP", "OBJCOPY", "OBJDUMP", "CPPFLAGS",
        "CFLAGS", "CXXFLAGS", "LDFLAGS", "LDLIBS", "DEFS", "VPATH",
        "GPATH", "OBJS", "PLANG", "INCS", "LIBS", "EDIR", "ODIR",
        "SDIR", "INCLUDE", "COMPILER_PATH", "GCC_EXEC_PREFIX",
    )
    if any(os.environ.get(name, "").strip() for name in override_names):
        return False
    reviewed_search_roots = {
        "CPATH": {"/usr/include", "/usr/local/include",
                  "/opt/homebrew/include"},
        "CPLUS_INCLUDE_PATH": {"/usr/include", "/usr/local/include",
                               "/opt/homebrew/include"},
        "C_INCLUDE_PATH": {"/usr/include", "/usr/local/include",
                           "/opt/homebrew/include"},
        "OBJC_INCLUDE_PATH": {"/usr/include", "/usr/local/include",
                              "/opt/homebrew/include"},
        "LIBRARY_PATH": {"/usr/lib", "/usr/local/lib",
                         "/opt/homebrew/lib"},
    }
    for name, reviewed in reviewed_search_roots.items():
        value = os.environ.get(name, "").strip()
        if value:
            paths = value.split(os.pathsep)
            if any(not path or path not in reviewed for path in paths):
                return False
    return True


def _make_entrypoint_overrides() -> list[str]:
    """Return precedence makefiles that are not the reviewed Makefile inode."""
    reviewed = ROOT / "Makefile"
    overrides: list[str] = []
    for name in ("GNUmakefile", "makefile"):
        candidate = ROOT / name
        if not candidate.is_file():
            continue
        try:
            same_reviewed_file = candidate.samefile(reviewed)
        except OSError:
            same_reviewed_file = False
        if not same_reviewed_file:
            overrides.append(name)
    return overrides


def _has_unreviewed_macro_directive(code: str) -> bool:
    """Reject source macros except conventional empty include guards.

    The protected seam is deliberately checked fail-closed: even a macro whose
    spelling does not mention the protected members can change access labels,
    the overflow guard, or synthesize a member name with token pasting.
    """
    directive = re.compile(
        rf"^\s*{_CPP_DIRECTIVE_PREFIX}\s*(define|undef)\b([^\n]*)",
        re.MULTILINE)
    for match in directive.finditer(code):
        if match.group(1) != "define":
            return True
        definition = re.fullmatch(r"\s*([A-Za-z_]\w*)\s*", match.group(2))
        if not definition:
            return True
        name = definition.group(1)
        if not _INCLUDE_GUARD_NAME.fullmatch(name):
            return True
        guard = re.compile(
            rf"^\s*{_CPP_DIRECTIVE_PREFIX}\s*ifndef\s+"
            rf"{re.escape(name)}\b", re.MULTILINE)
        if not guard.search(code):
            return True
    return False


def _has_conditional_directive(code: str) -> bool:
    """Report conditional preprocessing in a protected implementation file."""
    return bool(re.search(
        rf"^\s*{_CPP_DIRECTIVE_PREFIX}\s*"
        r"(?:if|ifdef|ifndef|elif|else|endif)\b",
        code, re.MULTILINE))


def _has_source_inclusion_directive(code: str) -> bool:
    """Report source inclusion inside a protected C++ scope."""
    return bool(re.search(
        rf"^\s*{_CPP_DIRECTIVE_PREFIX}\s*"
        r"(?:include|include_next|import)\b",
        code, re.MULTILINE))


def _has_preprocessor_directive(code: str) -> bool:
    """Report any preprocessing directive inside a protected C++ scope."""
    return bool(re.search(
        rf"^\s*{_CPP_DIRECTIVE_PREFIX}\s*[A-Za-z_]\w*\b",
        code, re.MULTILINE))


def _has_nested_source_inclusion(code: str) -> bool:
    """Reject fragment expansion inside any scanned brace scope."""
    directive = re.compile(
        rf"^\s*{_CPP_DIRECTIVE_PREFIX}\s*"
        r"(?:include|include_next|import)\b", re.MULTILINE)
    return any(code[:match.start()].count("{") !=
               code[:match.start()].count("}")
               for match in directive.finditer(code))


def _mask_cpp_conditionals(code: str) -> str:
    """Exclude every conditional-preprocessor region from positive evidence."""
    masked: list[str] = []
    depth = 0
    directive = re.compile(
        rf"^\s*{_CPP_DIRECTIVE_PREFIX}\s*([A-Za-z_]\w*)\b")
    for line in code.splitlines(keepends=True):
        match = directive.match(line)
        if match:
            name = match.group(1)
            if name in {"if", "ifdef", "ifndef"}:
                depth += 1
            elif name == "endif":
                depth = max(0, depth - 1)
            masked.append("".join(
                "\n" if character == "\n" else " " for character in line))
        elif depth:
            masked.append("".join(
                "\n" if character == "\n" else " " for character in line))
        else:
            masked.append(line)
    return "".join(masked)


def _direct_access_label(code: str, position: int):
    depth = 0
    access = None
    for token in re.finditer(
            r"[{}]|\b(public|protected|private)\s*:", code[:position]):
        if token.group(0) == "{":
            depth += 1
        elif token.group(0) == "}":
            depth = max(0, depth - 1)
        elif depth == 0:
            access = token.group(1)
    return access, depth


def _unique_braced_scope(code: str, signature_pattern: str):
    matches = list(re.finditer(
        signature_pattern, code, re.MULTILINE | re.DOTALL))
    if len(matches) != 1:
        return None
    signature = matches[0]
    opening = code.rfind("{", signature.start(), signature.end())
    if opening < 0:
        return None
    depth = 1
    cursor = opening + 1
    while cursor < len(code) and depth:
        if code[cursor] == "{":
            depth += 1
        elif code[cursor] == "}":
            depth -= 1
        cursor += 1
    if depth:
        return None
    return signature.start(), code[opening + 1:cursor - 1]


def _direct_scope_matches(code: str, pattern: re.Pattern[str]):
    """Return pattern matches that are direct statements in this brace scope."""
    direct = []
    for match in pattern.finditer(code):
        prefix = code[:match.start()]
        if prefix.count("{") == prefix.count("}"):
            direct.append(match)
    return direct


def _scope_begins_with(code: str, pattern: re.Pattern[str]) -> bool:
    """Require the named direct statement to be the scope's first code."""
    match = pattern.search(code)
    direct_starts = {candidate.start()
                     for candidate in _direct_scope_matches(code, pattern)}
    return bool(match and not code[:match.start()].strip()
                and match.start() in direct_starts)


def _scope_contract_sha256(code: str) -> str:
    """Hash the reviewed lexical scope while ignoring formatting whitespace."""
    normalized = re.sub(r"\s+", " ", code).strip().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def _topology_invalidation_seam_errors(
        mesh_header: str,
        mesh_source: str,
        flat_source: str,
        other_mesh_sources: list[str],
        require_complete_source_surface: bool = False,
        transaction_source: str = "") -> list[str]:
    lexical_code = [_cpp_code(source) for source in (
        mesh_header, mesh_source, flat_source, transaction_source,
        *other_mesh_sources)]
    unconditional_code = [_mask_cpp_conditionals(code) for code in lexical_code]
    header_code, mesh_code, flat_code, transaction_code, *other_code = (
        unconditional_code)
    all_lexical_code = "\n".join(lexical_code)
    all_code = "\n".join(unconditional_code)

    reset_pattern = re.compile(
        r"\bregularLimitSurfaceRowCache_\s*\.\s*invalidate\s*\(\s*\)\s*;")
    seam_call_pattern = re.compile(
        r"\binvalidate_topology_derived_state\s*\(\s*\)\s*;")
    setup_generation_call_pattern = re.compile(
        r"\bmark_topology_generation_installed_by_setup\s*"
        r"\(\s*\)\s*;")
    transaction_seam_call_pattern = re.compile(
        r"\bmesh_\s*\.\s*invalidate_topology_derived_state\s*"
        r"\(\s*\)\s*;")
    seam_definition_pattern = re.compile(
        r"\bvoid\s+(?:Mesh::)?invalidate_topology_derived_state\s*"
        r"\(\s*\)\s*\{")
    setup_generation_definition_pattern = re.compile(
        r"\bvoid\s+(?:Mesh::)?"
        r"mark_topology_generation_installed_by_setup\s*"
        r"\(\s*\)\s*(?:noexcept\s*)?\{")
    generation_pattern = re.compile(r"\btopologyGeneration_\b")
    setup_generation_pattern = re.compile(
        r"\btopologyGenerationInstalledBySetup_\b")
    reviewed_seam_body_pattern = re.compile(
        r"\s*if\s*\(\s*topologyGeneration_\s*==\s*"
        r"std::numeric_limits\s*<\s*std::uint64_t\s*>\s*::\s*max\s*"
        r"\(\s*\)\s*\)\s*\{\s*"
        r"throw\s+std::overflow_error\s*\(\s*\)\s*;\s*\}\s*"
        r"regularLimitSurfaceRowCache_\s*\.\s*invalidate\s*"
        r"\(\s*\)\s*;\s*\+\+\s*topologyGeneration_\s*;\s*")
    errors: list[str] = []

    if require_complete_source_surface and (
            len(other_mesh_sources) != _REVIEWED_OTHER_SOURCE_COUNT or
            _source_inclusion_surface_sha256(other_mesh_sources) !=
            _REVIEWED_OTHER_INCLUSION_SHA256):
        errors.append("all-source include surface has drifted")
    if any(_has_nested_source_inclusion(code) for code in lexical_code[4:]):
        errors.append("source inclusion occurs inside an unreviewed scope")

    reviewed_sources = [
        ("Mesh header", mesh_header, _REVIEWED_MESH_HEADER_INCLUDES),
        ("import setup", mesh_source, _REVIEWED_IMPORT_INCLUDES),
        ("flat setup", flat_source, _REVIEWED_FLAT_INCLUDES),
    ]
    if transaction_source:
        reviewed_sources.append((
            "topology transaction", transaction_source,
            _REVIEWED_TRANSACTION_INCLUDES))
    for name, source, expected in reviewed_sources:
        reviewed = tuple(("include", operand) for operand in expected)
        if _source_inclusion_directives(source) != reviewed:
            errors.append(f"{name} include surface has drifted")

    protected_code = [
        ("Mesh header", lexical_code[0]),
        ("import setup", lexical_code[1]),
        ("flat setup", lexical_code[2]),
    ]
    if transaction_source:
        protected_code.append(("topology transaction", lexical_code[3]))
    for name, code in protected_code:
        if _has_conditional_directive(code):
            errors.append(f"{name} contains conditional preprocessing")

    mesh_class = _unique_braced_scope(
        lexical_code[0], r"\bclass\s+Mesh\b[^;{]*\{")
    if mesh_class is None:
        errors.append("unique Mesh class scope")
    else:
        _, class_body = mesh_class
        if _has_preprocessor_directive(class_body):
            errors.append("Mesh class contains unreviewed preprocessing")
        seam_scope = _unique_braced_scope(
            class_body,
            r"\bvoid\s+invalidate_topology_derived_state\s*\(\s*\)\s*\{")
        if seam_scope is None:
            errors.append("unique topology invalidation seam definition")
        else:
            seam_start, seam_body = seam_scope
            access, seam_depth = _direct_access_label(class_body, seam_start)
            if access != "private" or seam_depth != 0:
                errors.append("topology invalidation seam is not private")
            if len(reset_pattern.findall(seam_body)) != 1:
                errors.append("cache reset is not owned exactly once by seam")
            elif len(_direct_scope_matches(seam_body, reset_pattern)) != 1:
                errors.append("cache reset is not a direct seam statement")
            if not reviewed_seam_body_pattern.fullmatch(seam_body):
                errors.append("topology invalidation seam body has drifted")
        setup_generation_scope = _unique_braced_scope(
            class_body,
            r"\bvoid\s+mark_topology_generation_installed_by_setup\s*"
            r"\(\s*\)\s*noexcept\s*\{")
        if setup_generation_scope is None:
            errors.append("unique setup-generation marker definition")
        else:
            marker_start, marker_body = setup_generation_scope
            access, marker_depth = _direct_access_label(
                class_body, marker_start)
            if access != "private" or marker_depth != 0:
                errors.append("setup-generation marker is not private")
            if not re.fullmatch(
                    r"\s*topologyGenerationInstalledBySetup_\s*=\s*"
                    r"topologyGeneration_\s*;\s*", marker_body):
                errors.append("setup-generation marker body has drifted")
        setup_generation_accessor = _unique_braced_scope(
            class_body,
            r"\bstd::uint64_t\s+"
            r"topology_generation_installed_by_setup\s*\(\s*\)\s*"
            r"const\s*noexcept\s*\{")
        if setup_generation_accessor is None:
            errors.append("unique setup-generation accessor definition")
        else:
            accessor_start, accessor_body = setup_generation_accessor
            access, accessor_depth = _direct_access_label(
                class_body, accessor_start)
            if access != "public" or accessor_depth != 0:
                errors.append("setup-generation accessor is not public")
            if not re.fullmatch(
                    r"\s*return\s+topologyGenerationInstalledBySetup_\s*;\s*",
                    accessor_body):
                errors.append("setup-generation accessor body has drifted")
        setup_generation_member = list(re.finditer(
            r"\bstd::uint64_t\s+topologyGenerationInstalledBySetup_\s*=\s*"
            r"0\s*;", class_body))
        if len(setup_generation_member) != 1:
            errors.append("setup-generation storage has drifted")
        else:
            access, member_depth = _direct_access_label(
                class_body, setup_generation_member[0].start())
            if access != "private" or member_depth != 0:
                errors.append("setup-generation storage is not private")
        if transaction_source:
            friend_pattern = re.compile(
                r"\bfriend\s+class\s+"
                r"slimed::loop_topology::LoopTopologyTransaction\s*;")
            friend_matches = list(friend_pattern.finditer(class_body))
            if len(friend_matches) != 1:
                errors.append("transaction is not the unique seam friend")
            else:
                access, friend_depth = _direct_access_label(
                    class_body, friend_matches[0].start())
                if access != "private" or friend_depth != 0:
                    errors.append("transaction seam friendship is not private")

    import_scope = _unique_braced_scope(
        lexical_code[1],
        r"\bvoid\s+Mesh::setup_from_vertices_faces\s*\([^)]*\)\s*\{")
    if import_scope is None:
        errors.append("unique import setup scope")
    elif _has_source_inclusion_directive(import_scope[1]):
        errors.append("import setup contains an unreviewed include")
    elif len(seam_call_pattern.findall(import_scope[1])) != 1:
        errors.append("import setup does not call seam exactly once")
    elif not _scope_begins_with(import_scope[1], seam_call_pattern):
        errors.append("import setup does not begin with a direct seam call")
    if import_scope is not None:
        if (len(setup_generation_call_pattern.findall(import_scope[1])) != 1 or
                len(_direct_scope_matches(
                    import_scope[1], setup_generation_call_pattern)) != 1):
            errors.append("import setup does not mark its generation exactly once")
        if (_scope_contract_sha256(import_scope[1]) !=
                _REVIEWED_IMPORT_SETUP_SHA256):
            errors.append("import setup body has drifted")

    flat_scope = _unique_braced_scope(
        lexical_code[2], r"\bvoid\s+Mesh::setup_flat\s*\(\s*\)\s*\{")
    if flat_scope is None:
        errors.append("unique flat setup scope")
    elif _has_source_inclusion_directive(flat_scope[1]):
        errors.append("flat setup contains an unreviewed include")
    elif len(seam_call_pattern.findall(flat_scope[1])) != 1:
        errors.append("flat setup does not call seam exactly once")
    elif not _scope_begins_with(flat_scope[1], seam_call_pattern):
        errors.append("flat setup does not begin with a direct seam call")
    if flat_scope is not None:
        if (len(setup_generation_call_pattern.findall(flat_scope[1])) != 1 or
                len(_direct_scope_matches(
                    flat_scope[1], setup_generation_call_pattern)) != 1):
            errors.append("flat setup does not mark its generation exactly once")
        if (_scope_contract_sha256(flat_scope[1]) !=
                _REVIEWED_FLAT_SETUP_SHA256):
            errors.append("flat setup body has drifted")

    if transaction_source:
        transaction_scope = _unique_braced_scope(
            transaction_code,
            r"\bLoopTopologyTransactionResult\s+"
            r"LoopTopologyTransaction::commit\s*\(\s*\)\s*noexcept\s*\{")
        if transaction_scope is None:
            errors.append("unique topology transaction commit scope")
        else:
            _, transaction_body = transaction_scope
            if (_scope_contract_sha256(transaction_body) !=
                    _REVIEWED_TRANSACTION_COMMIT_SHA256):
                errors.append("topology transaction commit body has drifted")
            if _has_source_inclusion_directive(transaction_body):
                errors.append("topology transaction contains an unreviewed include")
            if len(seam_call_pattern.findall(transaction_body)) != 1:
                errors.append("topology transaction does not call seam exactly once")
            transaction_try = _unique_braced_scope(
                transaction_body, r"\btry\s*\{")
            if transaction_try is None:
                errors.append("unique topology transaction invalidation try scope")
            else:
                try_start, try_body = transaction_try
                if (transaction_body[:try_start].count("{") !=
                        transaction_body[:try_start].count("}")):
                    errors.append("topology transaction invalidation is conditional")
                if not transaction_seam_call_pattern.fullmatch(
                        try_body.strip()):
                    errors.append("topology transaction invalidation try body has drifted")

    if len(reset_pattern.findall(all_code)) != 1:
        errors.append("cache reset exists outside the single seam")
    if len(seam_definition_pattern.findall(all_code)) != 1:
        errors.append("topology invalidation seam has unreviewed definitions")
    if len(setup_generation_definition_pattern.findall(all_code)) != 1:
        errors.append("setup-generation marker has unreviewed definitions")
    if len(setup_generation_call_pattern.findall(all_code)) != 2:
        errors.append("setup-generation marker has unreviewed callers")
    expected_call_count = 3 if transaction_source else 2
    if len(seam_call_pattern.findall(all_code)) != expected_call_count:
        errors.append("topology invalidation seam has unreviewed callers")
    if (len(generation_pattern.findall(header_code)) != 5 or
            len(generation_pattern.findall(all_code)) != 5):
        errors.append("topology generation has unreviewed references")
    if (len(setup_generation_pattern.findall(header_code)) != 3 or
            len(setup_generation_pattern.findall(all_code)) != 3):
        errors.append("setup generation has unreviewed references")
    if any(_has_unreviewed_macro_directive(code) for code in lexical_code):
        errors.append("topology invalidation identity is macro-shadowed")
    for name, pattern in (
            ("cache reset", reset_pattern),
            ("topology invalidation seam call", seam_call_pattern),
            ("topology invalidation seam definition", seam_definition_pattern),
            ("topology generation", generation_pattern)):
        if len(pattern.findall(all_lexical_code)) != len(pattern.findall(all_code)):
            errors.append(f"{name} appears in a preprocessor conditional")
    return errors


def _python_code(text: str) -> str:
    tokens = tokenize.generate_tokens(io.StringIO(text).readline)
    return tokenize.untokenize(
        token for token in tokens
        if token.type not in {tokenize.COMMENT, tokenize.STRING})


def _active_markdown_paragraph(text: str, marker: str) -> str:
    active = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    active = re.sub(
        r"^```[^\n]*\n.*?^```\s*$", "", active,
        flags=re.DOTALL | re.MULTILINE)
    start = active.find(marker)
    if start < 0:
        return ""
    end = active.find("\n\n", start)
    return active[start:] if end < 0 else active[start:end]


def _cpp_block_after(text: str, marker: str) -> str:
    code = _cpp_code(text)
    marker_offset = code.index(marker)
    opening = code.index("{", marker_offset + len(marker))
    depth = 0
    for offset in range(opening, len(code)):
        if code[offset] == "{":
            depth += 1
        elif code[offset] == "}":
            depth -= 1
            if depth == 0:
                return code[opening + 1:offset]
    raise ValueError(f"unterminated C++ block after {marker}")


def _route_block_is_guarded_terminal_return(
        text: str, condition: str, evaluator: str) -> bool:
    block = _cpp_block_after(text, f"if ({condition})")
    return (evaluator in block
            and "if (!routed.accepted)" in block
            and bool(re.search(r"\breturn\s*;\s*$", block)))


def _energy_field_order(text: str, marker: str) -> list[str]:
    block = _cpp_block_after(text, marker)
    return re.findall(r"\benergy\.(energy[A-Za-z0-9_]+)\b", block)


def _markdown_row_cells(text: str, decision: str) -> list[str]:
    for line in text.splitlines():
        if re.match(rf"^\|\s*{re.escape(decision)}(?::[^|]*)?\s*\|", line):
            return [cell.strip() for cell in line.strip().strip("|").split("|")]
    return []


def _markdown_named_row_cells(text: str, name: str) -> list[str]:
    marker = f"`{name}`"
    for line in text.splitlines():
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if cells and cells[0] == marker:
                return cells
    return []


def _markdown_named_float(text: str, name: str) -> float:
    cells = _markdown_named_row_cells(text, name)
    if len(cells) < 2:
        return float("nan")
    try:
        return float(cells[1].strip("`"))
    except ValueError:
        return float("nan")


def _source_float(text: str, pattern: str) -> float:
    match = re.search(pattern, text)
    return float(match.group(1)) if match else float("nan")


def _source_pending_or_float(text: str, pattern: str) -> str | float:
    match = re.search(pattern, text)
    if not match:
        return "missing"
    value = match.group(1)
    return value if value == "TBD" else float(value)


def _source_int(text: str, pattern: str) -> int:
    match = re.search(pattern, text)
    return int(match.group(1)) if match else -1


def _git_output(*arguments: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *arguments], cwd=ROOT, text=True,
            stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def _git_success(*arguments: str) -> bool:
    try:
        subprocess.check_call(
            ["git", *arguments], cwd=ROOT,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def _is_commit_sha(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{40}", value))


def _collect_package_linearity() -> dict[str, Any]:
    """Measure only commits introduced after this package left mainline."""
    mainline_head = _git_output(
        "rev-parse", "--verify", f"{MAINLINE_REF}^{{commit}}")
    fork_point = _git_output("merge-base", MAINLINE_REF, "HEAD")
    fork_is_ancestor = (
        _is_commit_sha(fork_point)
        and _git_success("merge-base", "--is-ancestor", fork_point, "HEAD")
    )
    merge_commits: list[str] | None = None
    if fork_is_ancestor:
        output = _git_output(
            "rev-list", "--min-parents=2", f"{fork_point}..HEAD")
        if output != "unavailable":
            merge_commits = list(filter(None, output.splitlines()))
    return {
        "linearity_ref": MAINLINE_REF,
        "observed_mainline_head": mainline_head,
        "mainline_ref_resolved": _is_commit_sha(mainline_head),
        "linearity_fork_point": fork_point,
        "linearity_fork_is_ancestor": fork_is_ancestor,
        "merge_commits_after_fork": merge_commits,
    }


def collect_inventory() -> dict[str, Any]:
    makefile = _text("Makefile")
    adr = _text("docs/adr_unified_loop_backend.md")
    plan = _text("docs/unified_irregular_loop_implementation_plan.md")
    bfr_plan = _text("docs/bfr_loop_backend_plan_macos.md")
    compute = _text("src/energy_force/Compute_energy_and_force_on_mesh.cpp")
    regular = _text("src/mesh/OpenSubdiv_regular_evaluator.cpp")
    mesh_header = _text("include/mesh/Mesh.hpp")
    mesh_setup_flat = _text("src/mesh/Mesh_setup_flat.cpp")
    topology_transaction = _text(
        "src/mesh/Loop_topology_transaction.cpp")
    seam_surface_suffixes = {
        ".cpp", ".cc", ".cxx", ".cu", ".mm",
        ".hpp", ".h", ".cuh", ".ipp", ".tpp", ".inl"}
    other_seam_sources = [
        _text(path.relative_to(ROOT).as_posix())
        for base in (ROOT / "src", ROOT / "include")
        for path in sorted(base.rglob("*"))
        if path.is_file() and path.suffix in seam_surface_suffixes
        and path.relative_to(ROOT).as_posix() not in {
            "include/mesh/Mesh.hpp", "src/mesh/Mesh.cpp",
            "src/mesh/Mesh_setup_flat.cpp",
            "src/mesh/Loop_topology_transaction.cpp"}
    ]
    v3 = _text("src/mesh/OpenSubdiv_valence3_row_provider.cpp")
    v4 = _text("src/mesh/OpenSubdiv_valence4_row_provider.cpp")
    v4_topology = _text("src/mesh/Valence4_topology_source_mapping.cpp")
    v4_loop = _text("src/energy_force/Valence4_face_loop_route_preflight.cpp")
    v5 = _text("src/mesh/OpenSubdiv_valence5_row_provider.cpp")
    v5_loop = _text("src/energy_force/Valence5_opensubdiv_face_loop.cpp")
    geometry = _text("src/mesh/Mesh.cpp")
    legacy_topology = _text("src/mesh/Mesh_setup_geometry.cpp")
    legacy_matrix = _text("src/mesh/Gauss_quadrature.cpp")
    source_keyed_hpp = _text("include/energy_force/Source_keyed_kernel_call.hpp")
    source_keyed_cpp = _text("src/energy_force/Source_keyed_kernel_call.cpp")
    output = _text("src/io/output.cpp")
    checkpoint_writer_scope = _unique_braced_scope(
        _cpp_code(output),
        r"\bbool\s+write_model_restart_checkpoint\s*\([^)]*\)\s*\{")
    checkpoint_writer_contract_sha256 = (
        _scope_contract_sha256(checkpoint_writer_scope[1])
        if checkpoint_writer_scope is not None else "unavailable")
    cuda_cpu = _text("src/cuda/Cuda_regular_geometry_cpu.cpp")
    cuda_device = _text("src/cuda/Cuda_mesh_state.cu")
    adaptive = _text("include/mesh/Adaptive_edge_flip_quality.hpp")
    example_params = _text("data/example/example.params")
    routing_gap_map = _text("docs/irregular_routing_evidence_gap_map.md")
    surface_characterization = _text(
        "tests/test_surface_geometry_characterization.cpp")
    fixture_inventory_test = _text("tests/test_irregular_fixture_inventory.py")
    corpus = _source_corpus()
    invalidation_seam_errors = _topology_invalidation_seam_errors(
        mesh_header, geometry, mesh_setup_flat, other_seam_sources,
        require_complete_source_surface=True,
        transaction_source=topology_transaction)

    observed_head = _git_output("rev-parse", "HEAD")
    wp0_reviewed_endpoint_commit = _git_output(
        "rev-parse", "--verify", f"{WP0_REVIEWED_ENDPOINT_SHA}^{{commit}}")
    changed_paths = sorted(filter(None, _git_output(
        "diff", "--name-only",
        f"{BASE_SHA}..{WP0_REVIEWED_ENDPOINT_SHA}").splitlines()))
    commit_count_text = _git_output("rev-list", "--count", f"{BASE_SHA}..HEAD")
    commit_count = (int(commit_count_text)
                    if commit_count_text.isdigit() else -1)
    package_linearity = _collect_package_linearity()

    build_flags = sorted(set(re.findall(
        r"^(USE_OPENSUBDIV_[A-Z0-9_]+)\s*\?=", makefile, re.MULTILINE)))
    runtime_flags = sorted(set(re.findall(
        r'"(SLIMED_USE_OPENSUBDIV_[A-Z0-9_]+)"', corpus)))
    volume_factor_names = sorted(set(re.findall(
        r"\b(k[A-Za-z0-9_]*Volume[A-Za-z0-9_]*(?:Factor|Functional|Mode))\b",
        corpus)))
    volume_functional_tokens = sorted(set(match.lower() for match in re.findall(
        r"\b(?:legacy[_-]?x[_-]?volume|full[_-]?divergence[_-]?volume|"
        r"volume[_-]?functional|volume[_-]?mode)\b", corpus,
        flags=re.IGNORECASE)))
    pr176_face_loop = _git_output(
        "show", f"{PR176_SHA}:src/energy_force/Valence3_opensubdiv_face_loop.cpp")
    pr182_face_loop = _git_output(
        "show", f"{PR182_SHA}:src/energy_force/Valence3_opensubdiv_face_loop.cpp")

    d8_paragraph = _active_markdown_paragraph(
        adr, "Proposed D8 performance inputs are frozen")
    performance_budget = {
        "generic_vs_cached_regular_median": _source_pending_or_float(
            d8_paragraph,
            r"generic_vs_cached_regular_median\s*<=\s*(TBD|[0-9.]+)"),
        "generic_vs_direct_regular_each_case": _source_float(
            d8_paragraph,
            r"generic_vs_direct_regular_each_case\s*<=\s*([0-9.]+)"),
    }
    d8_pending_anchor_counts = {
        relative: _text(relative).count(
            "generic_vs_cached_regular_median <= TBD")
        for relative in EXPECTED_D8_PENDING_ANCHOR_COUNTS
    }
    d8_numeric_substitutions = {
        relative: re.findall(
            r"generic_vs_cached_regular_median\s*<=\s*([0-9.]+)",
            _text(relative))
        for relative in EXPECTED_D8_PENDING_ANCHOR_COUNTS
    }
    d8_direct_anchor_counts = {
        relative: _text(relative).count(
            "generic_vs_direct_regular_each_case <= 2.00")
        for relative in EXPECTED_D8_DIRECT_ANCHOR_COUNTS
    }
    performance_protocol = {
        "coordinate_only_steady_state": "coordinate-only\nsteady state" in d8_paragraph,
        "same_binary": "same-binary" in d8_paragraph,
        "alternating_order": "alternating-order" in d8_paragraph,
        "warmup_repeats": "warmup-plus-repeat" in d8_paragraph,
        "preparation_separate_once_per_epoch": _all_present(d8_paragraph, [
            "Topology preparation is reported separately",
            "occurs once per epoch",
        ]),
        "platform_variance_review": "reviewed\nfor platform variance" in d8_paragraph,
    }

    decisions = {
        decision: (_markdown_row_cells(adr, decision) + ["missing"])[1]
        for decision in EXPECTED_DECISIONS
    }
    plan_authorities = {
        decision: (_markdown_row_cells(plan, decision) +
                   ["missing", "missing", "missing"])[2]
        for decision in EXPECTED_PLAN_AUTHORITIES
    }
    observed_tolerances = copy.deepcopy(EXPECTED_TOLERANCES)
    observed_tolerances["regular_row_and_route_parity"]["value"] = _source_float(
        regular, r"kOpenSubdivRegularRowTolerance\s*=\s*([0-9.eE+-]+)")
    observed_tolerances["regular_residual_scale_floor"]["value"] = _source_float(
        regular, r"kOpenSubdivRegularResidualScaleFloor\s*=\s*([0-9.eE+-]+)")
    observed_tolerances["valence3_row_invariants"]["value"] = _source_float(
        v3, r"kInvariantTolerance\s*=\s*([0-9.eE+-]+)")
    observed_tolerances["valence4_row_invariants"]["value"] = _source_float(
        v4, r"coefficientSum\s*-\s*expectedSum\)\s*>\s*([0-9.eE+-]+)")
    observed_tolerances["valence5_row_invariants"]["value"] = _source_float(
        v5, r"kInvariantTolerance\s*=\s*([0-9.eE+-]+)")
    observed_tolerances["valence5_reviewed_production_parity"]["value"] = _source_float(
        _text("include/energy_force/Valence5_opensubdiv_face_loop.hpp"),
        r"kReviewedProductionTolerance\s*=\s*([0-9.eE+-]+)")
    observed_tolerances["irregular_serial_openmp_envelope"]["value"] = _source_float(
        _text("docs/irregular_serial_omp_tolerance_characterization.md"),
        r"tolerance envelope is `([0-9.eE+-]+)` absolute")

    fixtures = {path: _sha256(path) for path in EXPECTED_FIXTURE_HASHES}
    b2p_fixtures = {
        path: _sha256(path) for path in EXPECTED_B2P_FIXTURE_HASHES
        if (ROOT / path).is_file()
    }
    b2p_family_metadata_path = (
        "data/fixtures/candidates/b2p_single_flip_family/family_metadata.json")
    b2p_family_metadata = json.loads(_text(b2p_family_metadata_path)) \
        if (ROOT / b2p_family_metadata_path).is_file() else {}
    b2p_locality_sample_manifest = b2p_family_metadata.get(
        "locality_sample_manifest", {})
    b2p_targets = {
        name: {
            "adr": _markdown_named_float(adr, name),
            "bfr_plan": _markdown_named_float(bfr_plan, name),
        }
        for name in EXPECTED_B2P_TARGETS
    }
    b2p_oracle_contract = {
        "all_required_fields_present": _all_present(
            bfr_plan, EXPECTED_B2P_ORACLE_ANCHORS),
        "anchors": {
            anchor: anchor in bfr_plan
            for anchor in EXPECTED_B2P_ORACLE_ANCHORS
        },
        "d10_plan_status": (
            _markdown_row_cells(bfr_plan, "D10") + ["missing"]
        )[1],
        "d10_adr_approved": _all_present(adr, [
            "Frozen B2p / D10 targets (approved)",
            "explicitly approved D10 on 2026-08-08",
            "Approval accepts the frozen coverage challenge and changes no value",
        ]),
        "official_opensubdiv_tag_commit": (
            bfr_plan.count("9dab8a47bfbb1388ec8388fe61f5f916e6123f38") == 1
        ),
        "execution_and_evidence_anchors": {
            anchor: anchor in bfr_plan
            for anchor in EXPECTED_B2P_EXECUTION_AND_EVIDENCE_ANCHORS
        },
    }
    b2p_claim_scan_text = "\n".join([
        bfr_plan,
        adr,
        *[
            _text(path) for path in EXPECTED_B2P_FIXTURE_HASHES
            if path.endswith(".json") and (ROOT / path).is_file()
        ],
    ]).lower()
    b2p_forbidden_claim_tokens = [
        token for token in FORBIDDEN_B2P_CLAIM_TOKENS
        if token in b2p_claim_scan_text
    ]
    readiness_fixtures = {
        path: _sha256(path) for path in EXPECTED_B2_READINESS_FIXTURE_HASHES
        if (ROOT / path).is_file()
    }
    readiness_manifest_path = (
        "data/fixtures/candidates/b2_readiness_v1/execution_manifest.json")
    readiness_manifest = json.loads(_text(readiness_manifest_path)) \
        if (ROOT / readiness_manifest_path).is_file() else {}
    readiness_entries = readiness_manifest.get("entries", [])
    readiness_source_row_ids = [
        entry.get("source_matrix_row_id") for entry in readiness_entries]
    readiness_execution_case_ids = [
        entry.get("execution_case_id") for entry in readiness_entries]
    readiness_alias_pairs = [
        [entry.get("execution_case_id"), entry.get("alias_of")]
        for entry in readiness_entries if entry.get("alias_of") is not None
    ]
    readiness_by_case = {
        entry.get("execution_case_id"): entry for entry in readiness_entries
    }
    readiness_alias_contracts_valid = True
    for contract in readiness_manifest.get("alias_contracts", []):
        alias = readiness_by_case.get(contract.get("alias_execution_case_id"), {})
        canonical = readiness_by_case.get(
            contract.get("canonical_execution_case_id"), {})
        if alias.get("alias_of") != canonical.get("execution_case_id"):
            readiness_alias_contracts_valid = False
        for field in contract.get("must_equal_fields", []):
            if alias.get(field) != canonical.get(field):
                readiness_alias_contracts_valid = False
        actual_differences = sorted(
            key for key in set(alias).union(canonical)
            if alias.get(key) != canonical.get(key)
        )
        if actual_differences != sorted(contract.get("permitted_differences", [])):
            readiness_alias_contracts_valid = False

    readiness_unique_content_identities: list[str] = []
    readiness_valid_thread_content_identities: list[str] = []
    for entry in readiness_entries:
        if entry.get("alias_of") is not None:
            continue
        input_spec = entry.get("input", {})
        if input_spec.get("kind") == "checked_in_fixture":
            content_keys = [member.get("content_identity_key")
                            for member in input_spec.get("members", [])]
        elif input_spec.get("kind") == "deterministic_mutation":
            content_keys = [input_spec.get("output_content_identity_key")]
        else:
            content_keys = []
        for content_key in content_keys:
            if content_key not in readiness_unique_content_identities:
                readiness_unique_content_identities.append(content_key)
            if (entry.get("numeric_gate_applicability", {}).get(
                    "threading_bfr_only") and
                    content_key not in readiness_valid_thread_content_identities):
                readiness_valid_thread_content_identities.append(content_key)

    expected_entry_fields = {
        "alias_of", "candidates", "corner_policy_ref", "execution_case_id",
        "face_policy", "input", "mesh_evidence_key",
        "numeric_gate_applicability", "row_order_ref", "sample_policy_ref",
        "source_matrix_checks", "source_matrix_row", "source_matrix_row_id",
    }
    readiness_entry_schema_complete = True
    for entry in readiness_entries:
        if set(entry) != expected_entry_fields:
            readiness_entry_schema_complete = False
        checks = entry.get("source_matrix_checks", [])
        if not checks or len({item.get("check_id") for item in checks}) != len(checks):
            readiness_entry_schema_complete = False
        for item in checks:
            applicability = item.get("b2_applicability")
            if applicability == "APPLICABLE":
                expected = {"b2_applicability", "check_id", "procedure", "source_text"}
            elif applicability == "N/A":
                expected = {"b2_applicability", "check_id", "reason", "source_text"}
            else:
                expected = set()
            if set(item) != expected or not item.get(
                    "procedure" if applicability == "APPLICABLE" else "reason"):
                readiness_entry_schema_complete = False

    readiness_sample_policies = readiness_manifest.get("sample_policies", [])
    readiness_sample_policy_ids = [item.get("id")
                                   for item in readiness_sample_policies]
    readiness_samples_by_id = {item.get("id"): item
                               for item in readiness_sample_policies}
    readiness_regular_samples_equal_b2p = (
        readiness_samples_by_id.get("regular_interior_l6_10", {}).get("samples") ==
        b2p_locality_sample_manifest.get("samples"))
    trend_samples = readiness_samples_by_id.get(
        "extraordinary_trend_24_per_corner", {}).get("samples", [])
    readiness_trend_samples_valid = len(trend_samples) == 24
    for offset, sample in enumerate(trend_samples):
        exponent, ray = 1 + offset // 3, offset % 3
        try:
            xi, eta = Fraction(sample["xi"]), Fraction(sample["eta"])
            readiness_trend_samples_valid = (
                readiness_trend_samples_valid and
                sample["radius_exponent"] == exponent and
                sample["ray_index"] == ray and
                sample["id"] == f"trend-r{exponent:02d}-ray{ray:02d}" and
                xi + eta == Fraction(1, 2 ** exponent))
        except (KeyError, ValueError, ZeroDivisionError):
            readiness_trend_samples_valid = False

    readiness_manifest_contract_sha256 = hashlib.sha256(json.dumps(
        readiness_manifest, sort_keys=True,
        separators=(",", ":")).encode("utf-8")).hexdigest()
    readiness_generator = _text("scripts/generate_b2_readiness_fixtures.py")
    readiness_generator_sha256 = hashlib.sha256(
        readiness_generator.encode("utf-8")).hexdigest()
    readiness_criteria = {
        name: {
            "adr": _markdown_named_float(adr, name),
            "bfr_plan": _source_float(
                bfr_plan,
                rf"`{re.escape(name)}`\s*\|\s*`<=\s*([0-9.]+)"),
        }
        for name in EXPECTED_B2_READINESS_CRITERIA
    }
    readiness_mutation_rules = readiness_manifest.get("mutation_rules", [])
    readiness_mutation_ids = [
        item.get("id") for item in readiness_mutation_rules
    ]
    coordinate_rule = next((item for item in readiness_mutation_rules
                            if item.get("id") == "coordinate_perturbation_v1"), {})
    coordinate_path = ROOT / coordinate_rule.get("base_member_path", "") / "vertices.csv"
    readiness_coordinate_bits_valid = coordinate_path.is_file()
    if readiness_coordinate_bits_valid:
        with coordinate_path.open(newline="", encoding="utf-8") as stream:
            coordinate_rows = list(csv.reader(stream))
        for axis, component in enumerate(coordinate_rule.get("components", [])):
            try:
                observed_input = float(coordinate_rows[1][axis])
                observed_delta = float.fromhex(component["delta_binary64_hex"])
                observed_output = observed_input + observed_delta
                pairs = [
                    (observed_input, component["input_binary64_hex"],
                     component["input_bits_hex"]),
                    (observed_delta, component["delta_binary64_hex"],
                     component["delta_bits_hex"]),
                    (observed_output, component["output_binary64_hex"],
                     component["output_bits_hex"]),
                ]
                readiness_coordinate_bits_valid = (
                    readiness_coordinate_bits_valid and
                    component.get("axis") == "xyz"[axis] and
                    all(value.hex() == hex_value and
                        struct.pack(">d", value).hex() == bits
                        for value, hex_value, bits in pairs))
            except (IndexError, KeyError, ValueError):
                readiness_coordinate_bits_valid = False

    readiness_byte_identity_groups_valid = True
    for group in readiness_manifest.get("byte_identity_groups", []):
        for filename in group.get("required_equal_files", []):
            contents = [(ROOT / member / filename).read_bytes()
                        for member in group.get("members", [])
                        if (ROOT / member / filename).is_file()]
            if (len(contents) != len(group.get("members", [])) or not contents or
                    any(content != contents[0] for content in contents[1:])):
                readiness_byte_identity_groups_valid = False

    plan_readiness_section = bfr_plan.split(
        "### 3.4 Approved D12 B2-readiness criteria and execution protocol", 1
    )[-1].split("\n## 4.", 1)[0]
    adr_readiness_section = adr.split(
        "### Approved D12 B2-readiness ledger", 1
    )[-1].split("\nExpected scientific values", 1)[0]
    readiness_claim_scan = "\n".join([
        plan_readiness_section, adr_readiness_section,
        json.dumps(readiness_manifest, sort_keys=True),
        *[_text(path) for path in EXPECTED_B2_READINESS_FIXTURE_HASHES
          if path.endswith("candidate_metadata.json") and (ROOT / path).is_file()],
    ]).lower()
    readiness_forbidden_claim_tokens = [
        token for token in FORBIDDEN_B2_READINESS_CLAIM_TOKENS
        if token in readiness_claim_scan
    ]
    readiness_contract = {
        "anchors": {anchor: anchor in bfr_plan
                    for anchor in EXPECTED_B2_READINESS_ANCHORS},
        "d12_adr_status": (_markdown_row_cells(adr, "D12") + ["missing"])[1],
        "d12_plan_status": (_markdown_row_cells(bfr_plan, "D12") + ["missing"])[1],
        "generator_id_present": (
            'GENERATOR_ID = "scripts/generate_b2_readiness_fixtures.py"'
            in readiness_generator),
        "generator_contract_digest_present": (
            EXPECTED_B2_READINESS_MANIFEST_CONTRACT_SHA256 in readiness_generator),
        "generator_sha256": readiness_generator_sha256,
        "generator_mutations_present": all(
            mutation in readiness_generator for mutation in [
                "coordinate_perturbation_v1", "reverse_face_zero_v1",
                "delete_face_zero_v1", "append_face_zero_v1"]),
        "alias_contracts_valid": readiness_alias_contracts_valid,
        "adr_contract_digest_present": (
            EXPECTED_B2_READINESS_MANIFEST_CONTRACT_SHA256 in adr),
        "byte_identity_groups_valid": readiness_byte_identity_groups_valid,
        "coordinate_mutation_bits_valid": readiness_coordinate_bits_valid,
        "entry_schema_complete": readiness_entry_schema_complete,
        "manifest_contract_sha256": readiness_manifest_contract_sha256,
        "manifest_schema_version": readiness_manifest.get("schema_version"),
        "manifest_status": readiness_manifest.get("status"),
        "mutation_ids": readiness_mutation_ids,
        "regular_samples_equal_b2p": readiness_regular_samples_equal_b2p,
        "sample_policy_ids": readiness_sample_policy_ids,
        "thread_tuple_count": (
            len(readiness_valid_thread_content_identities) *
            len(readiness_manifest.get("threading_protocol", {}).get(
                "levels_approxLevelSmooth", [])) *
            len(readiness_manifest.get("threading_protocol", {}).get("modes", [])) *
            len(readiness_manifest.get("threading_protocol", {}).get("workers", []))),
        "trend_samples_valid": readiness_trend_samples_valid,
    }
    topology = {
        "valence3_tetrahedron": {
            "vertices": 4, "faces": 4, "valence": 3,
            "oriented_faces": _csv_int_rows(
                "data/fixtures/candidates/closed_valence3_tetrahedron/faces.csv"),
            "source_guard_present": _all_present(v3, [
                "kApprovedFaceCount = 4", "kApprovedSourceCount = 4",
                "vertex.adjacentVertices.size() != 3u",
                "!actual.oneRingVertices.empty()",
            ]),
            "source_faces_match_fixture":
                _initializer_rows(v3, "kApprovedFaces", 3) ==
                EXPECTED_FACES["valence3_tetrahedron"],
        },
        "valence4_octahedron": {
            "vertices": 6, "faces": 8, "valence": 4,
            "oriented_faces": _csv_int_rows(
                "data/fixtures/candidates/closed_valence4_octahedron/faces.csv"),
            "source_guard_present": _all_present(v4_topology, [
                "kApprovedVertexCount = 6", "kApprovedFaceCount = 8",
                "vertex.adjacentVertices.size() != 4u",
                "!face.oneRingVertices.empty()",
            ]),
            "source_faces_match_fixture":
                _initializer_rows(v4_topology, "kApprovedOrientedFaces", 3) ==
                EXPECTED_FACES["valence4_octahedron"],
        },
        "valence5_icosahedron": {
            "vertices": 12, "faces": 20, "valence": 5,
            "oriented_faces": _csv_int_rows("data/fixtures/closed_valence5/faces.csv"),
            "source_guard_present": _all_present(v5, [
                "kApprovedFaceCount = 20", "kApprovedSourceCount = 12",
                "vertex.adjacentVertices.size() != 5u",
                "actual.adjacentVertices.size() != 3u",
            ]),
            "source_faces_match_fixture":
                _initializer_rows(v5, "kApprovedFaces", 3) ==
                EXPECTED_FACES["valence5_icosahedron"],
            "face_source_mapping_sha256": _rows_sha256(
                _initializer_rows(v5, "kApprovedFaceSources", 9)),
        },
        "legacy_11_control_predicate": {
            "admitted_corner_valences": [5, 5, 5],
            "matrix_intended_corner_valences": [5, 6, 6],
            "defect_confirmed": _all_present(legacy_topology, [
                "vertices[node0].adjacentVertices.size() == 5",
                "vertices[node1].adjacentVertices.size() == 5",
                "vertices[node2].adjacentVertices.size() == 5",
                "int d4, d7, d8;",
            ]) and _all_present(legacy_matrix, [
                "const int N = 6;", "const int N1 = 5;",
                "std::vector<std::vector<double>> SM4(11",
            ]),
        },
    }

    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "pending",
        "baseline": {
            "reviewed_wp0_base": BASE_SHA,
            "original_wp01_base": ORIGINAL_WP01_BASE_SHA,
            "observed_head": observed_head,
            "observed_head_commit": _git_output(
                "rev-parse", "--verify", "HEAD^{commit}"),
            "observed_merge_base": _git_output("merge-base", BASE_SHA, "HEAD"),
            "base_is_ancestor": _git_success(
                "merge-base", "--is-ancestor", BASE_SHA, "HEAD"),
            "commits_after_base": commit_count,
            **package_linearity,
            "wp0_reviewed_endpoint": WP0_REVIEWED_ENDPOINT_SHA,
            "observed_wp0_reviewed_endpoint_commit":
                wp0_reviewed_endpoint_commit,
            "wp0_base_is_ancestor_of_endpoint": _git_success(
                "merge-base", "--is-ancestor", BASE_SHA,
                WP0_REVIEWED_ENDPOINT_SHA),
            "wp0_endpoint_is_ancestor_of_head": _git_success(
                "merge-base", "--is-ancestor", WP0_REVIEWED_ENDPOINT_SHA,
                "HEAD"),
            "observed_wp0_reviewed_merge_base": _git_output(
                "merge-base", BASE_SHA, WP0_REVIEWED_ENDPOINT_SHA),
            "changed_paths_in_reviewed_wp0_range": changed_paths,
            "allowed_wp0_paths": EXPECTED_WP0_PATHS,
            "pr176_stack_root": PR176_SHA,
            "pr176_object_available": pr176_face_loop != "unavailable",
            "observed_pr176_merge_base": _git_output(
                "merge-base", PR176_SHA, BASE_SHA),
            "pr176_production_route_anchor":
                "evaluate_guarded_valence3_opensubdiv_production_route" in
                pr176_face_loop,
            "pr182_stack_head": PR182_SHA,
            "pr182_merge_base": PR182_MERGE_BASE,
            "observed_pr182_merge_base": _git_output("merge-base", PR182_SHA, BASE_SHA),
            "observed_pr182_pr176_merge_base": _git_output(
                "merge-base", PR182_SHA, PR176_SHA),
            "pr182_object_available": pr182_face_loop != "unavailable",
            "pr182_full_divergence_anchor":
                "kFullDivergenceVolumeQuadratureFactor" in pr182_face_loop
                and "dot(evaluated[0], areaVector)" in pr182_face_loop,
            "pr182_classification": (
                "unmerged stacked negative evidence limited to symmetric/asymmetric "
                "3/4/4 bipyramids, OpenSubdiv 3.7.0, isolation 5, depths 0-4, "
                "fixed parameters and recorded targets"),
            "pr182_current_main_production": False,
            "pr176_current_main_production": False,
            "current_main_valence3_runtime_route": False,
        },
        "decisions": decisions,
        "A_build_dependency": {
            "build_flags": build_flags,
            "dependency_root": "OPENSUBDIV_ROOT",
            "dependency_root_required_for_each_flag":
                all(f"{flag}=1 requires OPENSUBDIV_ROOT=" in makefile
                    for flag in EXPECTED_BUILD_FLAGS),
            "valence4_compile_macro": "USE_OPENSUBDIV_REGULAR",
            "valence4_macro_coupling_present": "#ifdef USE_OPENSUBDIV_REGULAR" in v4,
            "default_opensubdiv_free": all(
                re.search(rf"^{flag}\s*\?=\s*0\s*$", makefile, re.MULTILINE)
                for flag in EXPECTED_BUILD_FLAGS),
        },
        "B_runtime_routes": {
            "runtime_flags": runtime_flags,
            "regular_token_semantics": "truthy except empty, 0, false/FALSE, off/OFF",
            "regular_semantics_present": _all_present(regular, [
                'text != "0"', 'text != "false"', 'text != "FALSE"',
                'text != "off"', 'text != "OFF"']),
            "valence4_token_semantics": "exact string 1",
            "valence4_semantics_present":
                'std::string(value) == "1"' in v4_loop,
            "valence5_token_semantics": "exact string 1",
            "valence5_semantics_present":
                v5_loop.count('std::string(value) == "1"') >= 2,
            "v4_v5_conflict_rejected":
                "if (valence4RouteRequested && valence5RouteRequested)" in compute,
            "whole_mesh_route_terminal_returns": {
                "valence4": _route_block_is_guarded_terminal_return(
                    compute, "valence4RouteRequested",
                    "evaluate_guarded_valence4_opensubdiv_production_route"),
                "valence5": _route_block_is_guarded_terminal_return(
                    compute, "valence5RouteRequested",
                    "evaluate_guarded_valence5_opensubdiv_production_route"),
            },
        },
        "C_valence3_ancestry": {
            "current_main": "proof-only row provider; no runtime production selector",
            "pr182": "separate stacked V3 production/convergence evidence",
            "runtime_selector_absent_on_current_main":
                "SLIMED_USE_OPENSUBDIV_VALENCE3" not in runtime_flags,
        },
        "D_topology_guards": topology,
        "E_provider_policy": {
            "scheme": "stock OpenSubdiv Sdc::SCHEME_LOOP",
            "vertex_boundary": "VTX_BOUNDARY_EDGE_ONLY",
            "all_three_providers_bind_scheme_boundary": all(
                _all_present(text, ["Sdc::SCHEME_LOOP", "VTX_BOUNDARY_EDGE_ONLY"])
                for text in (v3, v4, v5)),
            "compile_version_pin": {"valence3": 30700, "valence4": None, "valence5": None},
            "only_valence3_pin_present":
                "OPENSUBDIV_VERSION_NUMBER != 30700" in v3
                and "OPENSUBDIV_VERSION_NUMBER" not in v4
                and "OPENSUBDIV_VERSION_NUMBER" not in v5,
            "ambient_version_qualified": False,
        },
        "F_regular_cache": {
            "schema_version": 1,
            "key_fields": [
                "OpenSubdiv version", "Loop scheme", "EDGE_ONLY boundary",
                "adaptive depth 3", "first derivatives", "second derivatives",
                "sizeof(double)", "row tolerance", "vertex/face cardinality",
                "face identity/boundary/ghost/connectivity/one-ring",
                "VWU", "quadrature coefficients", "shape functions",
            ],
            "coordinates_excluded": "coord" not in regular[
                regular.index("RegularCacheKey regular_limit_surface_cache_key"):
                regular.index("struct RefinerDeleter")],
            "mutex_guarded": "std::lock_guard<std::mutex> lock(cache.mutex_)" in regular,
            "invalidations": [
                "Mesh::setup_from_vertices_faces", "Mesh::setup_flat",
                "LoopTopologyTransaction::commit"],
            "only_reviewed_invalidations_present":
                not invalidation_seam_errors,
            "invalidation_seam_errors": invalidation_seam_errors,
        },
        "G_volume_functionals": {
            "enumerated_factor_names": volume_factor_names,
            "geometry": {
                "regular_mesh": "legacy x-only literal 0.16666666666",
                "valence4": "legacy x-only literal 0.16666666666",
                "valence5": "legacy x-only literal 0.16666666666",
                "cuda_cpu": "legacy x-only literal 0.16666666666",
                "cuda_device": "legacy x-only literal 0.16666666666",
            },
            "legacy_factor_literal": LEGACY_VOLUME_FACTOR_LITERAL,
            "legacy_factor_anchors_present": all(
                f"kLegacyVolumeQuadratureFactor = {LEGACY_VOLUME_FACTOR_LITERAL}" in text
                for text in (geometry, v4_loop, v5_loop, cuda_cpu, cuda_device)),
            "x_only_anchors_present": all([
                "evaluation.position.get(0, 0) * a_3.get(0, 0)" in geometry,
                "evaluated[0][0] * areaVector[0]" in v4_loop,
                "evaluated[0][0] * areaVector[0]" in v5_loop,
                "rows[0][0] * cross[0]" in cuda_cpu,
                "rows[0][0] * cross[0]" in cuda_device,
            ]),
            "global_volume_energy": "0.5 * param.uVol / param.vol0 * pow(param.vol - param.vol0, 2.0)" if
                "0.5 * param.uVol / param.vol0 * pow(param.vol - param.vol0, 2.0)" in compute else "missing",
            "force": "full-vector analytic derivative with /3",
            "force_anchor_present": "tmp_evol = uVol * (vol - vol0) / 3.0" in compute,
            "one_functional_claim_valid": False,
        },
        "H_source_keyed_seam": {
            "variable_original_source_ids":
                "std::vector<int> originalSourceIds" in source_keyed_hpp,
            "derivative_row_count": 7,
            "mixed_rows": [5, 6],
            "mixed_rows_must_match_exactly":
                "canonicalSample.rows[5].coefficients[source] !=" in source_keyed_cpp
                and "canonicalSample.rows[6].coefficients[source]" in source_keyed_cpp,
            "source_validation_present": _all_present(source_keyed_cpp, [
                "require_unique_source_ids", "duplicate original source id",
                "out-of-range or unmapped", "nonfinite row data"]),
            "guarded_transaction": _all_present(compute, [
                "validate_guarded_source_keyed_production_face_loop(",
                "execute_guarded_source_keyed_production_face_loop("]),
        },
        "I_tolerances_fixtures": {
            "tolerances": observed_tolerances,
            "source_anchors_present": all([
                "kOpenSubdivRegularRowTolerance = 5.0e-6" in regular,
                "kOpenSubdivRegularResidualScaleFloor = 1.0e-12" in regular,
                "kInvariantTolerance = 1.0e-12" in v3,
                "std::abs(coefficientSum - expectedSum) > 1.0e-12" in v4,
                "kInvariantTolerance = 1.0e-12" in v5,
                "kReviewedProductionTolerance = 1.0e-10" in
                    _text("include/energy_force/Valence5_opensubdiv_face_loop.hpp"),
                "The tolerance envelope is `1.0e-10` absolute" in
                    _text("docs/irregular_serial_omp_tolerance_characterization.md"),
            ]),
            "fixture_sha256": fixtures,
            "expected_values_policy":
                "fixture regressions are locks, not independent scientific oracles",
        },
        "I3_b2p_frozen_inputs": {
            "targets": b2p_targets,
            "expected_targets": EXPECTED_B2P_TARGETS,
            "fixture_sha256": b2p_fixtures,
            "expected_fixture_sha256": EXPECTED_B2P_FIXTURE_HASHES,
            "locality_sample_manifest": b2p_locality_sample_manifest,
            "expected_locality_sample_manifest":
                EXPECTED_B2P_LOCALITY_SAMPLE_MANIFEST,
            "oracle_contract": b2p_oracle_contract,
            "forbidden_claim_tokens": b2p_forbidden_claim_tokens,
            "expected_forbidden_claim_tokens": [],
            "row_invariants_remain_distinct": _all_present(bfr_plan, [
                "Position-row sum one",
                "derivative-row sum zero",
                "separate `1.0e-12` invariants",
            ]),
        },
        "I4_b2_readiness_pending_inputs": {
            "alias_pairs": readiness_alias_pairs,
            "contract": readiness_contract,
            "criteria": readiness_criteria,
            "expected_criteria": EXPECTED_B2_READINESS_CRITERIA,
            "expected_fixture_sha256": EXPECTED_B2_READINESS_FIXTURE_HASHES,
            "execution_case_ids": readiness_execution_case_ids,
            "fixture_sha256": readiness_fixtures,
            "forbidden_claim_tokens": readiness_forbidden_claim_tokens,
            "source_row_ids": readiness_source_row_ids,
            "unique_content_identities": readiness_unique_content_identities,
            "valid_thread_content_identities":
                readiness_valid_thread_content_identities,
        },
        "I2_scope_performance": {
            "regular_n6_masks_coincide": {
                "neighbor": 1.0 / 16.0,
                "center": 5.0 / 8.0,
            },
            "primary_workload": {
                "is_flat": bool(re.search(
                    r"^isFlat\s*=\s*true\b", example_params, re.MULTILINE)),
                "boundary_type": "Periodic" if re.search(
                    r"^boundaryType\s*=\s*Periodic\b", example_params,
                    re.MULTILINE) else "missing",
                "physical_faces": _source_int(
                    _cpp_code(surface_characterization),
                    r"EXPECT_EQ\(physicalRegularFaces,\s*(\d+)\)"),
                "ghost_faces": _source_int(
                    _cpp_code(surface_characterization),
                    r"EXPECT_EQ\(ghostFaces,\s*(\d+)\)"),
                "mixed_valence_ghost_faces": _source_int(
                    _cpp_code(surface_characterization),
                    r"EXPECT_EQ\(ghostMixedValenceFaces,\s*(\d+)\)"),
                "prose_count_anchor_present": _all_present(routing_gap_map, [
                    "all 2,720 physical faces are regular",
                    "all 336 mixed-valence faces belong to the 960-face periodic ghost band",
                ]),
                "executable_count_anchors_present": _all_present(
                    _python_code(fixture_inventory_test), [
                        "self.assertEqual(sum(flag is True for flag in mesh.face_ghost_flags), 960)",
                        "inventory.BOUNDARY_ROUTE: 960",
                        "inventory.REGULAR_ROUTE: 2720",
                        "self.assertEqual(sum(flags), 960)",
                    ]),
            },
            "performance_budget": performance_budget,
            "performance_protocol": performance_protocol,
            "pending_cached_median_anchor_counts": d8_pending_anchor_counts,
            "numeric_cached_median_substitutions": d8_numeric_substitutions,
            "direct_case_anchor_counts": d8_direct_anchor_counts,
            "performance_budget_status": "candidate pending reproduction and explicit user approval",
        },
        "J_output_checkpoint": {
            "energy_csv_fields": _energy_field_order(
                output, "void write_energy_csv_fields"),
            "checkpoint_energy_write_fields": _energy_field_order(
                output, "void write_energy_terms"),
            "checkpoint_energy_read_fields": _energy_field_order(
                output, "bool read_energy_terms"),
            "energy_force_csv_appends": "meanForce",
            "precision": 17,
            "checkpoint_tag": "SLIMED_RESTART_V2",
            "checkpoint_atomic_temp_suffix": ".tmp",
            "checkpoint_atomic_rename": "std::rename(tempFilepath.c_str(), filepath.c_str())" in output,
            "checkpoint_writer_contract_sha256":
                checkpoint_writer_contract_sha256,
            "checkpoint_source_surface_sha256":
                _checkpoint_source_surface_sha256(),
            "checkpoint_make_entrypoint_overrides":
                _make_entrypoint_overrides(),
            "checkpoint_make_override_environment_absent":
                _make_override_environment_absent(),
            "checkpoint_preprocessor_surface_locked":
                _only_reviewed_preprocessor_includes(
                    output, _REVIEWED_CHECKPOINT_INCLUDES),
            "checkpoint_topology_write_interlock": _all_present(output, [
                "model.mesh.topology_generation() !=",
                "model.mesh.topology_generation_installed_by_setup()",
                "The V1/V2 restart formats do not store connectivity.",
            ]),
            "field_order_anchor_present": _all_present(output, [
                "energy.energyCurvature << ','", "energy.energyArea << ','",
                "energy.energyVolume << ','", "energy.energyTotal",
                "outfile << std::setprecision(17)", 'outfile << "SLIMED_RESTART_V2\\n"',
            ]),
            "backend_or_functional_metadata_present": any(token in output for token in [
                "subdivisionBackend", "volumeFunctional", "legacy-x-volume",
                "full-divergence-volume"]),
        },
        "K_deferred_lanes": {
            "adaptive_edge_flip": "proof-only quality predicate",
            "adaptive_header_namespace":
                "namespace slimed::adaptive_edge_flip_proof" in adaptive,
            "adaptive_production_call_count": corpus.count("evaluate_edge_flip_quality(") - 1,
            "adaptive_runtime_flag_present": bool(re.search(
                r'SLIMED_[A-Z0-9_]*(?:EDGE_FLIP|FLIP_EDGE)', corpus)),
            "cuda_policy": "frozen through WP0-WP7",
            "cuda_changed_from_exact_base": bool(_git_output(
                "diff", "--name-only", BASE_SHA, "--", "src/cuda", "include/cuda")),
        },
        "L_fail_closed": {
            "allowed_build_flags": EXPECTED_BUILD_FLAGS,
            "allowed_runtime_flags": EXPECTED_RUNTIME_FLAGS,
            "allowed_volume_factor_names": EXPECTED_VOLUME_FACTOR_NAMES,
            "allowed_volume_functional_tokens": EXPECTED_VOLUME_FUNCTIONAL_TOKENS,
            "observed_volume_functional_tokens": volume_functional_tokens,
            "plan_decision_authorities": plan_authorities,
            "expected_plan_decision_authorities": EXPECTED_PLAN_AUTHORITIES,
        },
    }
    return report


def validate_inventory(report: dict[str, Any], check_adr: bool = True) -> list[str]:
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    try:
        require(report["schema_version"] == 1, "schema version drift")
        baseline = report["baseline"]
        require(baseline["reviewed_wp0_base"] == BASE_SHA,
                "reviewed WP0 base SHA drift")
        require(baseline["original_wp01_base"] == ORIGINAL_WP01_BASE_SHA,
                "original WP0.1 base drift")
        require(baseline["observed_head"] not in {"unavailable", BASE_SHA},
                "HEAD missing or not beyond the pinned base")
        require(baseline["observed_head_commit"] == baseline["observed_head"],
                "observed HEAD identity drift")
        require(baseline["observed_merge_base"] == BASE_SHA,
                "HEAD/base merge ancestry drift")
        require(baseline["base_is_ancestor"], "pinned base is not an ancestor of HEAD")
        require(baseline["commits_after_base"] > 0, "WP0 commit sequence missing")
        require(baseline["linearity_ref"] == MAINLINE_REF,
                "linearity reference drift")
        require(baseline["mainline_ref_resolved"] and
                _is_commit_sha(baseline["observed_mainline_head"]),
                f"{MAINLINE_REF} is missing or unresolvable; fetch mainline "
                "history before checking package linearity")
        require(_is_commit_sha(baseline["linearity_fork_point"]),
                "mainline fork point missing or unresolvable")
        require(baseline["linearity_fork_is_ancestor"],
                "mainline fork point is not an ancestor of HEAD")
        require(baseline["merge_commits_after_fork"] == [],
                "unexpected merge commit in package branch")
        require(baseline["wp0_reviewed_endpoint"] == WP0_REVIEWED_ENDPOINT_SHA,
                "WP0 reviewed endpoint drift")
        require(baseline["observed_wp0_reviewed_endpoint_commit"] ==
                WP0_REVIEWED_ENDPOINT_SHA,
                "WP0 reviewed endpoint missing or unresolvable")
        require(baseline["wp0_base_is_ancestor_of_endpoint"],
                "WP0 reviewed endpoint/base ancestry drift")
        require(baseline["wp0_endpoint_is_ancestor_of_head"],
                "WP0 reviewed endpoint is not an ancestor of HEAD")
        require(baseline["observed_wp0_reviewed_merge_base"] == BASE_SHA,
                "WP0 reviewed range merge-base drift")
        require(baseline["allowed_wp0_paths"] == EXPECTED_WP0_PATHS,
                "WP0 path allowlist drift")
        require(baseline["changed_paths_in_reviewed_wp0_range"] ==
                EXPECTED_WP0_PATHS,
                "reviewed WP0 aggregate diff path drift")
        require(baseline["pr176_stack_root"] == PR176_SHA,
                "PR 176 root SHA drift")
        require(baseline["pr176_object_available"] and
                baseline["pr176_production_route_anchor"],
                "PR 176 production root object/route anchor missing")
        require(baseline["observed_pr176_merge_base"] == PR182_MERGE_BASE,
                "PR 176/current-main ancestry drift")
        require(baseline["pr182_stack_head"] == PR182_SHA, "PR 182 SHA drift")
        require(baseline["observed_pr182_merge_base"] == PR182_MERGE_BASE,
                "PR 182 ancestry drift")
        require(baseline["observed_pr182_pr176_merge_base"] == PR176_SHA,
                "PR 182 is not stacked directly on the reviewed PR 176 head")
        require(baseline["pr182_object_available"] and
                baseline["pr182_full_divergence_anchor"],
                "PR 182 evidence object/functional anchor missing")
        require(not baseline["pr176_current_main_production"] and
                not baseline["pr182_current_main_production"],
                "PR 176/182 ancestry conflated with current main")
        require(not baseline["current_main_valence3_runtime_route"], "false V3 runtime claim")
        require(report["decisions"] == EXPECTED_DECISIONS, "decision authority/status drift")

        a = report["A_build_dependency"]
        require(a["build_flags"] == EXPECTED_BUILD_FLAGS, "unlisted/missing build backend flag")
        require(a["dependency_root"] == "OPENSUBDIV_ROOT", "dependency root drift")
        require(a["dependency_root_required_for_each_flag"], "dependency root guard missing")
        require(a["valence4_compile_macro"] == "USE_OPENSUBDIV_REGULAR", "V4 macro coupling drift")
        require(a["valence4_macro_coupling_present"], "V4 macro coupling anchor missing")
        require(a["default_opensubdiv_free"], "default OpenSubdiv-free build drift")

        b = report["B_runtime_routes"]
        require(b["runtime_flags"] == EXPECTED_RUNTIME_FLAGS, "unlisted/missing runtime backend flag")
        require(b["regular_token_semantics"] ==
                "truthy except empty, 0, false/FALSE, off/OFF",
                "regular runtime token contract drift")
        require(b["valence4_token_semantics"] == "exact string 1" and
                b["valence5_token_semantics"] == "exact string 1",
                "V4/V5 runtime token contract drift")
        require(b["regular_semantics_present"], "regular truthy semantics drift")
        require(b["valence4_semantics_present"] and b["valence5_semantics_present"],
                "V4/V5 exact-1 semantics drift")
        require(b["v4_v5_conflict_rejected"] and
                b["whole_mesh_route_terminal_returns"] == {
                    "valence4": True, "valence5": True},
                "extraordinary route conflict/early-return drift")

        c = report["C_valence3_ancestry"]
        require(c["runtime_selector_absent_on_current_main"], "V3 current-main route appeared")

        d = report["D_topology_guards"]
        for name, expected_faces in EXPECTED_FACES.items():
            require(d[name]["oriented_faces"] == expected_faces,
                    f"{name} orientation/count/order drift")
            require(d[name]["source_guard_present"], f"{name} topology source guard drift")
            require(d[name]["source_faces_match_fixture"],
                    f"{name} source/fixture face identity drift")
        require((d["valence3_tetrahedron"]["vertices"],
                 d["valence3_tetrahedron"]["faces"],
                 d["valence3_tetrahedron"]["valence"]) == (4, 4, 3),
                "valence3 topology summary drift")
        require((d["valence4_octahedron"]["vertices"],
                 d["valence4_octahedron"]["faces"],
                 d["valence4_octahedron"]["valence"]) == (6, 8, 4),
                "valence4 topology summary drift")
        require((d["valence5_icosahedron"]["vertices"],
                 d["valence5_icosahedron"]["faces"],
                 d["valence5_icosahedron"]["valence"]) == (12, 20, 5),
                "valence5 topology summary drift")
        require(d["legacy_11_control_predicate"]["admitted_corner_valences"] == [5, 5, 5],
                "legacy predicate classification drift")
        require(d["legacy_11_control_predicate"]["matrix_intended_corner_valences"] == [5, 6, 6],
                "legacy matrix classification drift")
        require(d["legacy_11_control_predicate"]["defect_confirmed"],
                "legacy 11-control defect anchor missing")
        require(d["valence5_icosahedron"]["face_source_mapping_sha256"] ==
                EXPECTED_VALENCE5_FACE_SOURCE_MAPPING_SHA256,
                "valence5 exact face-source mapping drift")

        e = report["E_provider_policy"]
        require(e["all_three_providers_bind_scheme_boundary"], "scheme/boundary drift")
        require(e["compile_version_pin"] == {"valence3": 30700, "valence4": None, "valence5": None},
                "provider version policy drift")
        require(e["only_valence3_pin_present"], "version-pin anchor drift")
        require(not e["ambient_version_qualified"], "ambient version falsely qualified")

        f = report["F_regular_cache"]
        require(f["schema_version"] == 1 and len(f["key_fields"]) == 13,
                "regular cache schema/key drift")
        require(f["coordinates_excluded"], "coordinates entered regular cache key")
        require(f["mutex_guarded"], "regular cache mutex drift")
        require(f["invalidations"] == [
                    "Mesh::setup_from_vertices_faces", "Mesh::setup_flat",
                    "LoopTopologyTransaction::commit"],
                "regular cache invalidation list drift")
        require(f["only_reviewed_invalidations_present"], "regular cache invalidation anchor drift")

        g = report["G_volume_functionals"]
        require(g["enumerated_factor_names"] == EXPECTED_VOLUME_FACTOR_NAMES,
                "unlisted/missing volume functional factor")
        require(g["legacy_factor_literal"] == LEGACY_VOLUME_FACTOR_LITERAL and
                g["legacy_factor_anchors_present"],
                "legacy volume decimal literal drift")
        require(g["x_only_anchors_present"], "legacy x-only geometry anchor drift")
        require(g["global_volume_energy"] != "missing", "global volume energy anchor missing")
        require(g["force_anchor_present"], "full-vector /3 force anchor missing")
        require(not g["one_functional_claim_valid"], "false one-functional claim")

        h = report["H_source_keyed_seam"]
        require(h["variable_original_source_ids"] and h["source_validation_present"],
                "source-keyed identity validation drift")
        require(h["derivative_row_count"] == 7 and h["mixed_rows"] == [5, 6],
                "seven-row compatibility schema drift")
        require(h["mixed_rows_must_match_exactly"], "mixed-row duplication contract drift")
        require(h["guarded_transaction"], "guarded transaction anchor drift")

        i = report["I_tolerances_fixtures"]
        require(i["tolerances"] == EXPECTED_TOLERANCES, "named tolerance ledger drift")
        require(i["source_anchors_present"], "named tolerance source anchor drift")
        require(i["fixture_sha256"] == EXPECTED_FIXTURE_HASHES, "fixture SHA256 drift")

        i3 = report["I3_b2p_frozen_inputs"]
        require(i3["expected_targets"] == EXPECTED_B2P_TARGETS,
                "B2p target expectation drift")
        require(i3["targets"] == {
                    name: {"adr": value, "bfr_plan": value}
                    for name, value in EXPECTED_B2P_TARGETS.items()
                }, "B2p D10 target ledger drift")
        require(i3["expected_fixture_sha256"] == EXPECTED_B2P_FIXTURE_HASHES,
                "B2p fixture-hash expectation drift")
        require(i3["fixture_sha256"] == EXPECTED_B2P_FIXTURE_HASHES,
                "B2p fixture missing or SHA256 drift")
        require(i3["expected_locality_sample_manifest"] ==
                EXPECTED_B2P_LOCALITY_SAMPLE_MANIFEST,
                "B2p locality-manifest expectation drift")
        require(i3["locality_sample_manifest"] ==
                EXPECTED_B2P_LOCALITY_SAMPLE_MANIFEST,
                "B2p locality sample manifest drift")
        oracle = i3["oracle_contract"]
        require(oracle["all_required_fields_present"] and
                all(oracle["anchors"].values()),
                "B2p oracle contract incomplete")
        require(all(oracle["execution_and_evidence_anchors"].values()),
                "B2p execution or evidence-deduplication contract incomplete")
        require(oracle["d10_plan_status"] ==
                "Approved - Frozen B2p targets and coverage challenge accepted "
                "for B2 proof. This does not qualify Bfr, decide D9a or D9b, "
                "widen a target, or authorize production.",
                "D10 plan approval status drift")
        require(oracle["d10_adr_approved"],
                "D10 ADR approval boundary missing")
        require(oracle["official_opensubdiv_tag_commit"],
                "B2p OpenSubdiv 3.7.0 source pin drift")
        require(i3["forbidden_claim_tokens"] ==
                i3["expected_forbidden_claim_tokens"] == [],
                "B2p contains a candidate result or qualification claim")

        i4 = report["I4_b2_readiness_pending_inputs"]
        require(i4["expected_criteria"] == EXPECTED_B2_READINESS_CRITERIA,
                "B2 readiness criterion expectation drift")
        require(i4["criteria"] == {
                    name: {"adr": value, "bfr_plan": value}
                    for name, value in EXPECTED_B2_READINESS_CRITERIA.items()
                }, "B2 readiness criterion ledger drift")
        require(i4["expected_fixture_sha256"] ==
                EXPECTED_B2_READINESS_FIXTURE_HASHES,
                "B2 readiness fixture-hash expectation drift")
        require(i4["fixture_sha256"] == EXPECTED_B2_READINESS_FIXTURE_HASHES,
                "B2 readiness fixture missing or SHA256 drift")
        require(i4["source_row_ids"] == EXPECTED_B2_READINESS_SOURCE_ROW_IDS,
                "B2 readiness source-matrix row omission or reordering")
        require(i4["execution_case_ids"] ==
                EXPECTED_B2_READINESS_EXECUTION_CASE_IDS and
                len(set(i4["execution_case_ids"])) == 17,
                "B2 readiness execution-case identity drift")
        require(i4["alias_pairs"] == EXPECTED_B2_READINESS_ALIAS_PAIRS,
                "B2 readiness alias mapping drift")
        require(i4["unique_content_identities"] ==
                EXPECTED_B2_READINESS_UNIQUE_CONTENT_IDENTITIES,
                "B2 readiness unique mesh-evidence aggregation drift")
        require(i4["valid_thread_content_identities"] ==
                EXPECTED_B2_READINESS_VALID_THREAD_CONTENT_IDENTITIES,
                "B2 readiness threading fixture expansion drift")
        require(i4["forbidden_claim_tokens"] == [],
                "B2 readiness contains a forbidden result or qualification claim")
        readiness = i4["contract"]
        require(all(readiness["anchors"].values()),
                "B2 readiness protocol incomplete")
        require(readiness["d12_plan_status"] ==
                "Approved - B2 readiness criteria, schema-2 execution manifest, "
                "fixture corpus, and exact qualification/build protocol are "
                "frozen for B2. This does not qualify Bfr, decide D9a/D9b or "
                "D8, or authorize production.",
                "D12 plan status drift")
        require(readiness["d12_adr_status"] ==
                "Approved - B2 readiness criteria, schema-2 execution manifest, "
                "fixture corpus, and exact qualification/build protocol are "
                "frozen for B2. This does not qualify Bfr, decide D9a/D9b or "
                "D8, or authorize production.",
                "D12 ADR status drift")
        require(readiness["generator_id_present"] and
                readiness["generator_contract_digest_present"] and
                readiness["generator_mutations_present"],
                "B2 readiness generator/manifest cross-check failed")
        require(readiness["generator_sha256"] ==
                EXPECTED_B2_READINESS_GENERATOR_SHA256,
                "B2 readiness generator source drift")
        require(readiness["manifest_contract_sha256"] ==
                EXPECTED_B2_READINESS_MANIFEST_CONTRACT_SHA256,
                "B2 readiness manifest contract/rationale drift")
        require(readiness["adr_contract_digest_present"],
                "B2 readiness ADR/manifest contract cross-check drift")
        require(readiness["manifest_schema_version"] == 2 and
                readiness["manifest_status"] == "pending_D12",
                "B2 readiness frozen pre-decision manifest state drift")
        require(readiness["mutation_ids"] == [
                    "coordinate_perturbation_v1", "reverse_face_zero_v1",
                    "delete_face_zero_v1", "append_face_zero_v1"],
                "B2 readiness mutation rule omission or reordering")
        require(readiness["entry_schema_complete"],
                "B2 readiness entry/source-check schema incomplete")
        require(readiness["alias_contracts_valid"],
                "B2 readiness row-specific alias contract drift")
        require(readiness["byte_identity_groups_valid"],
                "B2 readiness shared fixture-byte evidence drift")
        require(readiness["coordinate_mutation_bits_valid"],
                "B2 readiness coordinate mutation binary64 drift")
        require(readiness["sample_policy_ids"] ==
                EXPECTED_B2_READINESS_SAMPLE_POLICY_IDS and
                readiness["regular_samples_equal_b2p"] and
                readiness["trend_samples_valid"],
                "B2 readiness sample policy omission/order/formula drift")
        require(readiness["thread_tuple_count"] == 588,
                "B2 readiness threading Cartesian product drift")
        require(i3["row_invariants_remain_distinct"],
                "B2p row invariants conflated with accuracy targets")

        i2 = report["I2_scope_performance"]
        require(i2["regular_n6_masks_coincide"] == {
                    "neighbor": 1.0 / 16.0, "center": 5.0 / 8.0},
                "regular N=6 mask-equivalence rationale drift")
        primary = i2["primary_workload"]
        require(primary == {
                    "is_flat": True,
                    "boundary_type": "Periodic",
                    "physical_faces": 2720,
                    "ghost_faces": 960,
                    "mixed_valence_ghost_faces": 336,
                    "prose_count_anchor_present": True,
                    "executable_count_anchors_present": True,
                }, "primary periodic/ghost workload scope drift")
        require(i2["performance_budget"] == EXPECTED_PERFORMANCE_BUDGET,
                "candidate D8 performance budget drift")
        require(i2["pending_cached_median_anchor_counts"] ==
                EXPECTED_D8_PENDING_ANCHOR_COUNTS,
                "pending D8 cached-median anchor drift")
        require(i2["numeric_cached_median_substitutions"] == {
                    relative: []
                    for relative in EXPECTED_D8_PENDING_ANCHOR_COUNTS
                }, "numeric D8 cached-median ceiling appeared before approval")
        require(i2["direct_case_anchor_counts"] ==
                EXPECTED_D8_DIRECT_ANCHOR_COUNTS,
                "candidate D8 direct-case ceiling anchor drift")
        require(i2["performance_protocol"] == {
                    "coordinate_only_steady_state": True,
                    "same_binary": True,
                    "alternating_order": True,
                    "warmup_repeats": True,
                    "preparation_separate_once_per_epoch": True,
                    "platform_variance_review": True,
                }, "candidate D8 performance protocol drift")
        require(i2["performance_budget_status"] ==
                "candidate pending reproduction and explicit user approval",
                "D8 performance budget authority drift")

        j = report["J_output_checkpoint"]
        require(j["energy_csv_fields"] == EXPECTED_ENERGY_FIELDS,
                "energy CSV field order drift")
        require(j["checkpoint_energy_write_fields"] == EXPECTED_ENERGY_FIELDS and
                j["checkpoint_energy_read_fields"] == EXPECTED_ENERGY_FIELDS,
                "checkpoint energy field order drift")
        require(j["energy_csv_fields"] == j["checkpoint_energy_write_fields"] ==
                j["checkpoint_energy_read_fields"],
                "CSV/checkpoint energy order disagreement")
        require(j["energy_force_csv_appends"] == "meanForce", "EnergyForce CSV suffix drift")
        require(j["precision"] == 17 and j["checkpoint_tag"] == "SLIMED_RESTART_V2",
                "output precision/checkpoint tag drift")
        require(j["checkpoint_atomic_temp_suffix"] == ".tmp" and j["checkpoint_atomic_rename"],
                "checkpoint atomic replacement drift")
        require(j["checkpoint_writer_contract_sha256"] ==
                _REVIEWED_CHECKPOINT_WRITER_SHA256,
                "checkpoint writer contract drift")
        require(j["checkpoint_source_surface_sha256"] ==
                _REVIEWED_CHECKPOINT_SOURCE_SURFACE_SHA256,
                "checkpoint source ownership drift")
        require(j["checkpoint_make_entrypoint_overrides"] == [],
                "checkpoint build entrypoint membership drift")
        require(j["checkpoint_make_override_environment_absent"],
                "checkpoint build entrypoint environment override")
        require(j["checkpoint_preprocessor_surface_locked"],
                "checkpoint writer preprocessing surface drift")
        require(j["checkpoint_topology_write_interlock"],
                "checkpoint topology write interlock missing")
        require(j["field_order_anchor_present"], "output/checkpoint source anchor drift")
        require(not j["backend_or_functional_metadata_present"],
                "false output backend/functional metadata claim")

        k = report["K_deferred_lanes"]
        require(k["adaptive_edge_flip"] == "proof-only quality predicate",
                "edge-flip status drift")
        require(k["adaptive_header_namespace"] and k["adaptive_production_call_count"] == 0,
                "edge-flip production call appeared")
        require(not k["adaptive_runtime_flag_present"], "edge-flip runtime flag appeared")
        require(k["cuda_policy"] == "frozen through WP0-WP7", "CUDA freeze drift")
        require(not k["cuda_changed_from_exact_base"], "CUDA changed in WP0.1")

        l = report["L_fail_closed"]
        require(l["allowed_build_flags"] == EXPECTED_BUILD_FLAGS, "build allowlist drift")
        require(l["allowed_runtime_flags"] == EXPECTED_RUNTIME_FLAGS, "runtime allowlist drift")
        require(l["allowed_volume_factor_names"] == EXPECTED_VOLUME_FACTOR_NAMES,
                "functional allowlist drift")
        require(l["allowed_volume_functional_tokens"] ==
                EXPECTED_VOLUME_FUNCTIONAL_TOKENS,
                "functional-token allowlist drift")
        require(l["observed_volume_functional_tokens"] ==
                EXPECTED_VOLUME_FUNCTIONAL_TOKENS,
                "unlisted volume functional token")
        require(l["expected_plan_decision_authorities"] ==
                EXPECTED_PLAN_AUTHORITIES,
                "plan authority allowlist drift")
        require(l["plan_decision_authorities"] == EXPECTED_PLAN_AUTHORITIES,
                "plan/user decision authority drift")
    except (KeyError, TypeError, IndexError) as error:
        errors.append(f"inventory schema incomplete: {error}")

    if check_adr:
        adr_path = ROOT / "docs/adr_unified_loop_backend.md"
        if not adr_path.is_file():
            errors.append("ADR missing")
        else:
            adr = _text("docs/adr_unified_loop_backend.md")
            for decision, status in EXPECTED_DECISIONS.items():
                if f"| {decision} | {status} |" not in adr:
                    errors.append(f"ADR/inventory disagreement for {decision}")
            for anchor in (BASE_SHA, ORIGINAL_WP01_BASE_SHA,
                           WP0_REVIEWED_ENDPOINT_SHA, PR176_SHA, PR182_SHA,
                           "D3 and D4 remain pending WP2.1, independent scientific review"):
                if anchor not in adr:
                    errors.append(f"ADR anchor missing: {anchor}")
            for name, value in EXPECTED_B2P_TARGETS.items():
                rendered = format(value, ".15g")
                if _markdown_named_float(adr, name) != value:
                    errors.append(f"ADR B2p target missing or changed: {name}={rendered}")
            for path, digest in EXPECTED_B2P_FIXTURE_HASHES.items():
                if f"| `{path}` | `{digest}` |" not in adr:
                    errors.append(f"ADR B2p fixture hash missing: {path}")
            for name, value in EXPECTED_B2_READINESS_CRITERIA.items():
                if _markdown_named_float(adr, name) != value:
                    errors.append(
                        f"ADR B2 readiness criterion missing or changed: {name}")
            for path, digest in EXPECTED_B2_READINESS_FIXTURE_HASHES.items():
                if f"| `{path}` | `{digest}` |" not in adr:
                    errors.append(f"ADR B2 readiness fixture hash missing: {path}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail on inventory drift")
    parser.add_argument("--json", action="store_true", help="emit complete JSON")
    arguments = parser.parse_args()

    report = collect_inventory()
    errors = validate_inventory(report)
    report["status"] = "ok" if not errors else "failed"
    report["errors"] = errors

    if arguments.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Unified Loop baseline inventory: {report['status']}")
        for error in errors:
            print(f"- {error}")
    return 1 if arguments.check and errors else 0


if __name__ == "__main__":
    sys.exit(main())
