import contextlib
import copy
from decimal import Decimal
import io
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_valence3_provider_and_science_harness_are_guarded_and_inventoried():
    provider = (ROOT / "src/mesh/OpenSubdiv_valence3_row_provider.cpp").read_text()
    harness = (
        ROOT / "experiments/irregular_valence3_opensubdiv_geometry_force.cpp"
    ).read_text()
    runner = (
        ROOT / "scripts/run_irregular_valence3_opensubdiv_geometry_force.py"
    ).read_text()
    workflow = (
        ROOT / ".github/workflows/valence3_opensubdiv_proof.yml"
    ).read_text()

    assert "USE_OPENSUBDIV_VALENCE3" in provider
    assert "phase1ProviderExplicitRequest" in provider
    assert "productionRouteEnabled = true" not in provider
    assert "Valence3TopologyKind::CanonicalTetrahedron" in provider
    assert "Valence3TopologyKind::TriangularBipyramid344" in provider
    assert '"closed valence-3 3/4/4 triangular bipyramid"' in provider
    assert "cachedRows[cacheIndex]" in provider
    assert "LimitStencilTableFactoryReal<double>" in provider
    assert "mixed.mixed345FacePresent" in harness
    assert "existing_slimed_energy_force_algebra_executed" in harness
    assert "element_energy_force_regular" in harness
    assert "finiteDifferenceVerified" in harness
    assert "maximum_transpose_relative_residual" in harness
    assert "transpose_identity_verified" in harness
    assert "prepare_source_keyed_kernel_call" in harness
    assert "scatter_source_keyed_face_forces_to_component_buffer" in harness
    assert "reduce_source_keyed_force_component_buffers" in harness
    assert "source_keyed_scatter_verified" in harness
    assert "net_force_relative_residual" in harness
    assert "net_torque_relative_residual" in harness
    assert "unsupported_mixed_force_imbalance_observed" in harness
    assert "phase2_mechanical_packet_started" in harness
    assert "max_finite_difference_relative_error" in harness
    assert "fullDivergenceVolumeConjugacyVerified" in harness
    assert "full_divergence_volume_energy_force_conjugate" in harness
    assert "legacy_x_only_volume_mismatch_resolved_for_valence3" in harness
    assert "fixture['full_divergence_volume']" in runner
    assert "fixture['legacy_volume']" not in runner
    assert "providerApplicable" in harness
    assert "providerRejectedWhenNotApplicable" in harness
    assert "normalsValidated" in harness
    assert "kDifferenceSteps" in harness
    assert "build_proof_rows(mesh, 4)" in harness
    assert "build_proof_rows(mesh, 6)" in harness
    assert "OPENSUBDIV_VERSION_NUMBER != 30700" in provider
    assert "immutableRowCacheHit" in (
        ROOT / "include/mesh/OpenSubdiv_valence3_row_provider.hpp"
    ).read_text()
    assert "Coordinates are deliberately" in provider
    assert "build_guarded_opensubdiv_valence3_rows" in harness
    assert "default_off_contract" in runner
    assert "-DUSE_OPENSUBDIV_VALENCE3" in runner
    assert "Build OpenSubdiv 3.7.0 CPU library" in workflow
    assert "--require-opensubdiv --json" in workflow


def test_valence3_candidate_fixtures_encode_closed_3_mixed_345_and_344_topologies():
    tetra = ROOT / "data/fixtures/candidates/closed_valence3_tetrahedron"
    mixed = ROOT / "data/fixtures/candidates/closed_mixed_valence345"
    bipyramid = (
        ROOT
        / "data/fixtures/candidates/closed_valence3_triangular_bipyramid"
    )
    asymmetric_bipyramid = (
        ROOT
        / "data/fixtures/candidates/asymmetric_valence3_triangular_bipyramid"
    )
    assert len((tetra / "vertices.csv").read_text().strip().splitlines()) == 4
    assert len((tetra / "faces.csv").read_text().strip().splitlines()) == 4
    assert len((mixed / "vertices.csv").read_text().strip().splitlines()) == 6
    assert len((mixed / "faces.csv").read_text().strip().splitlines()) == 8
    assert len((bipyramid / "vertices.csv").read_text().strip().splitlines()) == 5
    assert len((bipyramid / "faces.csv").read_text().strip().splitlines()) == 6
    assert len(
        (asymmetric_bipyramid / "vertices.csv").read_text().strip().splitlines()
    ) == 5
    assert len(
        (asymmetric_bipyramid / "faces.csv").read_text().strip().splitlines()
    ) == 6
    metadata = (mixed / "candidate_metadata.json").read_text()
    assert '"vertex_valence_by_id": [5, 5, 4, 3, 4, 3]' in metadata
    assert '"contains_face_valence_triplet": "3/4/5"' in metadata
    bipyramid_metadata = (bipyramid / "candidate_metadata.json").read_text()
    assert '"vertex_valence_by_id": [3, 3, 4, 4, 4]' in bipyramid_metadata
    assert bipyramid_metadata.count('"3/4/4"') == 6
    asymmetric_metadata = (
        asymmetric_bipyramid / "candidate_metadata.json"
    ).read_text()
    assert '"coordinate_delta_source_0": [0.071, -0.043, 0.029]' in asymmetric_metadata
    assert '"vertex_valence_by_id": [3, 3, 4, 4, 4]' in asymmetric_metadata


def test_phase5_bipyramid_remains_proof_only_and_production_stays_tetrahedral():
    header = (ROOT / "include/mesh/OpenSubdiv_valence3_row_provider.hpp").read_text()
    provider = (ROOT / "src/mesh/OpenSubdiv_valence3_row_provider.cpp").read_text()
    face_loop = (ROOT / "src/energy_force/Valence3_opensubdiv_face_loop.cpp").read_text()
    harness = (
        ROOT / "experiments/irregular_valence3_opensubdiv_geometry_force.cpp"
    ).read_text()
    runner = (
        ROOT / "scripts/run_irregular_valence3_opensubdiv_geometry_force.py"
    ).read_text()

    assert "TriangularBipyramid344" in header
    assert "Production callers" in header
    assert "request.topology" in provider
    assert "exactFiveSourceBoundaryValidated" in provider
    assert "exactFourSourceBoundaryValidated" in face_loop
    assert "rowRequest.topology" not in face_loop
    assert "bipyramid.allFacesAre344" in harness
    assert "asymmetric_valence3_triangular_bipyramid" in harness
    assert "topology_keyed_provider_cache_validated" in harness
    assert "repeatedProvider.immutableRowCacheHit" in harness
    assert "wrongTopologyRequest" in harness
    assert "BIPYRAMID" in runner
    assert "ASYMMETRIC_BIPYRAMID" in runner


def test_phase5_bipyramid_nested_quadrature_is_binding_and_fixed():
    harness = (
        ROOT / "experiments/irregular_valence3_opensubdiv_geometry_force.cpp"
    ).read_text()
    runner = (
        ROOT / "scripts/run_irregular_valence3_opensubdiv_geometry_force.py"
    ).read_text()

    assert "nested_quadrature_plan" in harness
    assert "kStudyMaximumDepth = 4" in harness
    assert "samplesPerFace" in harness
    assert "subtriangleWeight / kSampleCount" in harness
    assert "plan.s[sample] + plan.t[sample] >= 1.0" in harness
    assert "twoSuccessiveGlobalTargetsMet" in harness
    assert "twoSuccessiveForceTargetsMet" in harness
    assert "scientificTargetsMet" in harness
    assert "activationBlocked" in harness
    assert "studyCompleted" in harness
    assert "kStudyGlobalChangeTarget = 1.0e-6" in harness
    assert "kStudyForceChangeTarget = 1.0e-5" in harness
    assert "kStudyAdaptiveIsolationLevel = 5" in harness
    assert "build_proof_rows(mesh, kStudyAdaptiveIsolationLevel, plan)" in harness
    assert "<=\n            kStudyGlobalChangeTarget" in harness
    assert "<=\n            kStudyForceChangeTarget" in harness
    assert "bipyramidConvergence.passed" in harness
    assert "asymmetricBipyramidConvergence.passed" in harness
    assert "quadrature_convergence" in harness
    assert "broader_topology_activation_blocked" in harness
    assert "convergence['global_relative_changes']" in runner
    assert "validate_serialized_bipyramids" in runner
    assert "validate_convergence_payload" in runner
    assert "global_change_denominator" in harness
    assert "force_change_denominator" in harness
    assert "ASYMMETRIC_BIPYRAMID" in runner
    study = (
        ROOT / "docs/irregular_valence3_phase5_quadrature_convergence.md"
    ).read_text()
    assert "scientific_targets_met: false" in study
    assert "activation_blocked: true" in study
    assert "No tolerance was widened" in study


def test_phase5_human_runner_reports_quadrature_blocker():
    runner_path = (
        ROOT / "scripts/run_irregular_valence3_opensubdiv_geometry_force.py"
    )
    runner = runpy.run_path(str(runner_path))
    payload = {
        "status": "passed",
        "fixtures": [],
        "quadrature_convergence": [
            {
                "name": "asymmetric_valence3_triangular_bipyramid",
                "passed": True,
                "study_completed": True,
                "scientific_targets_met": False,
                "activation_blocked": True,
                "global_relative_changes": [2.3e-4],
                "force_relative_changes": [1.5e-2],
            }
        ],
    }
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        runner["emit"](payload, False)
    rendered = output.getvalue()
    assert "status: passed" in rendered
    assert "asymmetric_valence3_triangular_bipyramid quadrature" in rendered
    assert "evidence_packet_passed=True" in rendered
    assert "study_completed=True" in rendered
    assert "scientific_targets_met=False" in rendered
    assert "activation_blocked=True" in rendered
    assert "global_changes=[0.00023]" in rendered
    assert "force_changes=[0.015]" in rendered


def _valid_convergence_payload(runner):
    reports = []
    for name, expected in runner["EXPECTED_CONVERGENCE"].items():
        levels = []
        for index, depth in enumerate(runner["EXPECTED_DEPTHS"]):
            levels.append(
                {
                    "depth": depth,
                    "samples_per_face": runner["EXPECTED_SAMPLES"][index],
                    "plan_validated": True,
                    "rows_structurally_valid": True,
                    "rows_valid": index < 4,
                    "maximum_row_invariant_residual": (
                        1.0516032489249483e-12 if index == 4 else 1.0e-14
                    ),
                    "finite": True,
                    "area": expected["area"][index],
                    "full_divergence_volume": expected["volume"][index],
                    "bending_energy": expected["bending"][index],
                    "total_energy": expected["total"][index],
                }
            )
        reports.append(
            {
                "name": name,
                "levels": levels,
                "global_relative_changes": expected["global_changes"].copy(),
                "force_relative_changes": expected["force_changes"].copy(),
                "all_plans_validated": True,
                "all_rows_structurally_valid": True,
                "all_rows_valid": False,
                "all_finite": True,
                "two_successive_global_targets_met": False,
                "two_successive_force_targets_met": False,
                "scientific_targets_met": False,
                "activation_blocked": True,
                "study_completed": True,
                "passed": True,
            }
        )
    return {
        "status": "passed",
        "broader_topology_quadrature_targets_met": False,
        "broader_topology_activation_blocked": True,
        "quadrature_study_contract": copy.deepcopy(
            runner["EXPECTED_STUDY_CONTRACT"]
        ),
        "quadrature_convergence": reports,
    }


def test_phase5_runner_independently_rejects_mutated_convergence_evidence():
    runner = runpy.run_path(
        str(ROOT / "scripts/run_irregular_valence3_opensubdiv_geometry_force.py")
    )
    validate = runner["validate_convergence_payload"]
    valid = _valid_convergence_payload(runner)
    assert validate(valid)[0]

    mutations = []

    missing_report = copy.deepcopy(valid)
    missing_report["quadrature_convergence"].pop()
    mutations.append(missing_report)

    missing_field = copy.deepcopy(valid)
    del missing_field["quadrature_convergence"][0]["levels"][0]["area"]
    mutations.append(missing_field)

    nonfinite = copy.deepcopy(valid)
    nonfinite["quadrature_convergence"][0]["levels"][0]["total_energy"] = float(
        "nan"
    )
    mutations.append(nonfinite)

    wrong_sequence = copy.deepcopy(valid)
    wrong_sequence["quadrature_convergence"][0]["levels"][2]["depth"] = 3
    mutations.append(wrong_sequence)

    flipped_policy = copy.deepcopy(valid)
    flipped_policy["quadrature_convergence"][0]["activation_blocked"] = False
    mutations.append(flipped_policy)

    accidental_convergence = copy.deepcopy(valid)
    accidental_convergence["quadrature_convergence"][0][
        "global_relative_changes"
    ][-2:] = [1.0e-8, 1.0e-8]
    accidental_convergence["quadrature_convergence"][0][
        "two_successive_global_targets_met"
    ] = True
    mutations.append(accidental_convergence)

    changed_contract = copy.deepcopy(valid)
    changed_contract["quadrature_study_contract"]["maximum_depth"] = 5
    mutations.append(changed_contract)

    for mutation in mutations:
        assert not validate(mutation)[0]


def test_phase5_runner_binds_serialized_bipyramid_geometry_and_topology():
    runner = runpy.run_path(
        str(ROOT / "scripts/run_irregular_valence3_opensubdiv_geometry_force.py")
    )
    validate = runner["validate_bipyramid_fixture_data"]
    symmetric = copy.deepcopy(runner["EXPECTED_SYMMETRIC_BIPYRAMID_VERTICES"])
    asymmetric = copy.deepcopy(symmetric)
    asymmetric[0] = [
        Decimal("0.071"),
        Decimal("-0.043"),
        Decimal("1.029"),
    ]
    faces = copy.deepcopy(runner["EXPECTED_BIPYRAMID_FACES"])
    assert validate(symmetric, faces, asymmetric, faces)[0]

    changed_coordinate = copy.deepcopy(asymmetric)
    changed_coordinate[0][0] += Decimal("0.001")
    assert not validate(symmetric, faces, changed_coordinate, faces)[0]

    reversed_face = copy.deepcopy(faces)
    reversed_face[0] = list(reversed(reversed_face[0]))
    assert not validate(symmetric, reversed_face, asymmetric, faces)[0]

    missing_face = copy.deepcopy(faces[:-1])
    assert not validate(symmetric, missing_face, asymmetric, faces)[0]
