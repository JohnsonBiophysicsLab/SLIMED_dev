from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_valence3_phase3_face_loop_is_guarded_and_not_a_default_caller():
    header = (
        ROOT / "include/energy_force/Valence3_opensubdiv_face_loop.hpp"
    ).read_text()
    implementation = (
        ROOT / "src/energy_force/Valence3_opensubdiv_face_loop.cpp"
    ).read_text()
    experiment = (
        ROOT / "experiments/irregular_valence3_opensubdiv_face_loop.cpp"
    ).read_text()
    runner = (
        ROOT / "scripts/run_irregular_valence3_opensubdiv_face_loop.py"
    ).read_text()
    production_caller = (
        ROOT / "src/energy_force/Compute_energy_and_force_on_mesh.cpp"
    ).read_text()
    workflow = (
        ROOT / ".github/workflows/valence3_opensubdiv_proof.yml"
    ).read_text()

    assert "SLIMED_USE_OPENSUBDIV_VALENCE3_PHASE3" in implementation
    assert "scientificBaselineAcceptedExplicitRequest" in implementation
    assert "kFullDivergenceVolumeQuadratureFactor" in implementation
    assert "dot(evaluated[0], areaVector)" in implementation
    assert "build_guarded_opensubdiv_valence3_rows" in implementation
    assert "prepare_source_keyed_kernel_call" in implementation
    assert "validate_guarded_source_keyed_production_face_loop" in implementation
    assert "execute_guarded_source_keyed_production_face_loop" in implementation
    assert "evaluate_guarded_valence3_opensubdiv_production_route" in implementation
    assert "result.productionRouteEnabled = true" in implementation
    assert "result.defaultEvaluatorCaller = true" in implementation
    assert "result.phase4ActivationAuthorized = true" in implementation
    assert "fullDivergenceVolumeValidated = false" in header
    assert "volumeFunctionalDecisionPending = false" in header
    assert "productionRouteEnabled = false" in header
    assert "nonzero_volume_constraint_accepted" in experiment
    assert "nonzero_volume_force_verified" in experiment
    assert "full_divergence_volume_validated" in experiment
    assert "mixed_345_rejection_atomic" in experiment
    assert "complete_transaction_validated_before_mutation" in experiment
    assert "production_one_rings_preserved" in experiment
    assert "default_evaluator_still_unsupported" in experiment
    assert "SLIMED_USE_OPENSUBDIV_REGULAR" in experiment
    assert "unrelated_regular_token_isolated" in experiment
    assert "default_off_contract" in runner
    assert "-DUSE_OPENSUBDIV_VALENCE3" in runner
    assert "Valence3_opensubdiv_production_route.hpp" in production_caller
    assert "opensubdiv_valence3_production_routing_requested" in production_caller
    assert "extraordinaryRouteRequestCount" in production_caller
    assert "evaluate_guarded_valence3_opensubdiv_production_route" in production_caller
    assert "if (guardedSourceKeyedRows == nullptr)" in production_caller
    assert "assert_supported_membrane_force_routing(mesh);" in production_caller
    assert production_caller.count("if (guardedSourceKeyedRows == nullptr)") >= 2
    assert "run_irregular_valence3_opensubdiv_face_loop.py" in workflow
    assert "phase4_activation_validated" in experiment
    assert "production_wrapper_default_off_atomic" in experiment
    assert "conflicting_routes_rejection_atomic" in experiment
    assert "immutable_row_cache_validated" in experiment
    assert "output_checkpoint_round_trip_validated" in experiment
    assert "serial_openmp_repeat_validated" in runner
    assert '"-DOMP"' in runner
    assert "Valence3_opensubdiv_production_route.hpp" in (
        ROOT / "include/energy_force/Valence3_opensubdiv_production_route.hpp"
    ).read_text()


def test_phase3_files_do_not_touch_cuda_sources():
    phase3_paths = [
        ROOT / "include/energy_force/Valence3_opensubdiv_face_loop.hpp",
        ROOT / "src/energy_force/Valence3_opensubdiv_face_loop.cpp",
        ROOT / "experiments/irregular_valence3_opensubdiv_face_loop.cpp",
        ROOT / "scripts/run_irregular_valence3_opensubdiv_face_loop.py",
    ]
    assert all("cuda" not in path.as_posix().lower() for path in phase3_paths)
