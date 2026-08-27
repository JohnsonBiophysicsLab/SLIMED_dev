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
    assert len((tetra / "vertices.csv").read_text().strip().splitlines()) == 4
    assert len((tetra / "faces.csv").read_text().strip().splitlines()) == 4
    assert len((mixed / "vertices.csv").read_text().strip().splitlines()) == 6
    assert len((mixed / "faces.csv").read_text().strip().splitlines()) == 8
    assert len((bipyramid / "vertices.csv").read_text().strip().splitlines()) == 5
    assert len((bipyramid / "faces.csv").read_text().strip().splitlines()) == 6
    metadata = (mixed / "candidate_metadata.json").read_text()
    assert '"vertex_valence_by_id": [5, 5, 4, 3, 4, 3]' in metadata
    assert '"contains_face_valence_triplet": "3/4/5"' in metadata
    bipyramid_metadata = (bipyramid / "candidate_metadata.json").read_text()
    assert '"vertex_valence_by_id": [3, 3, 4, 4, 4]' in bipyramid_metadata
    assert bipyramid_metadata.count('"3/4/4"') == 6


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
