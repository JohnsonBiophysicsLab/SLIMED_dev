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

    assert "USE_OPENSUBDIV_VALENCE3" in provider
    assert "phase1ProviderExplicitRequest" in provider
    assert "productionRouteEnabled = true" not in provider
    assert "kApprovedSourceCount = 4" in provider
    assert "LimitStencilTableFactoryReal<double>" in provider
    assert "mixed.mixed345FacePresent" in harness
    assert "existing_slimed_energy_force_algebra_executed" in harness
    assert "element_energy_force_regular" in harness
    assert "finiteDifferenceVerified" in harness
    assert "max_finite_difference_relative_error" in harness
    assert "legacyVolumeForceMismatchObserved" in harness
    assert "legacy_x_only_volume_mismatch_is_a_production_blocker" in harness
    assert "build_guarded_opensubdiv_valence3_rows" in harness
    assert "default_off_contract" in runner
    assert "-DUSE_OPENSUBDIV_VALENCE3" in runner


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
