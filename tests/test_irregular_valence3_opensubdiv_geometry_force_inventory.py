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
    assert "kApprovedSourceCount = 4" in provider
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
    assert "providerApplicable" in harness
    assert "providerRejectedWhenNotApplicable" in harness
    assert "normalsValidated" in harness
    assert "kDifferenceSteps" in harness
    assert "build_proof_rows(mesh, 4)" in harness
    assert "build_proof_rows(mesh, 6)" in harness
    assert "OPENSUBDIV_VERSION_NUMBER != 30700" in provider
    assert "build_guarded_opensubdiv_valence3_rows" in harness
    assert "default_off_contract" in runner
    assert "-DUSE_OPENSUBDIV_VALENCE3" in runner
    assert "Build OpenSubdiv 3.7.0 CPU library" in workflow
    assert "--require-opensubdiv --json" in workflow


def test_valence3_candidate_fixtures_encode_closed_3_and_mixed_345_topologies():
    tetra = ROOT / "data/fixtures/candidates/closed_valence3_tetrahedron"
    mixed = ROOT / "data/fixtures/candidates/closed_mixed_valence345"
    assert len((tetra / "vertices.csv").read_text().strip().splitlines()) == 4
    assert len((tetra / "faces.csv").read_text().strip().splitlines()) == 4
    assert len((mixed / "vertices.csv").read_text().strip().splitlines()) == 6
    assert len((mixed / "faces.csv").read_text().strip().splitlines()) == 8
    metadata = (mixed / "candidate_metadata.json").read_text()
    assert '"vertex_valence_by_id": [5, 5, 4, 3, 4, 3]' in metadata
    assert '"contains_face_valence_triplet": "3/4/5"' in metadata
