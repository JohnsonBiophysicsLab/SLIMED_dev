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
    assert "mesh.param.uVol != 0.0" in implementation
    assert "legacy-volume/full-divergence decision" in implementation
    assert "build_guarded_opensubdiv_valence3_rows" in implementation
    assert "prepare_source_keyed_kernel_call" in implementation
    assert "validate_guarded_source_keyed_production_face_loop" in implementation
    assert "execute_guarded_source_keyed_production_face_loop" in implementation
    assert "productionRouteEnabled = true" not in implementation
    assert "defaultEvaluatorCaller = true" not in implementation
    assert "phase4ActivationAuthorized = true" not in implementation
    assert "volumeFunctionalDecisionPending = true" in header
    assert "productionRouteEnabled = false" in header
    assert "nonzero_volume_rejection_atomic" in experiment
    assert "mixed_345_rejection_atomic" in experiment
    assert "complete_transaction_validated_before_mutation" in experiment
    assert "production_one_rings_preserved" in experiment
    assert "default_evaluator_still_unsupported" in experiment
    assert "SLIMED_USE_OPENSUBDIV_REGULAR" in experiment
    assert "unrelated_regular_token_isolated" in experiment
    assert "default_off_contract" in runner
    assert "-DUSE_OPENSUBDIV_VALENCE3" in runner
    assert "evaluate_guarded_valence3_phase3_face_loop" not in production_caller
    assert "if (guardedSourceKeyedRows == nullptr)" in production_caller
    assert "assert_supported_membrane_force_routing(mesh);" in production_caller
    assert production_caller.count("if (guardedSourceKeyedRows == nullptr)") >= 2
    assert "run_irregular_valence3_opensubdiv_face_loop.py" in workflow


def test_phase3_files_do_not_touch_cuda_sources():
    phase3_paths = [
        ROOT / "include/energy_force/Valence3_opensubdiv_face_loop.hpp",
        ROOT / "src/energy_force/Valence3_opensubdiv_face_loop.cpp",
        ROOT / "experiments/irregular_valence3_opensubdiv_face_loop.cpp",
        ROOT / "scripts/run_irregular_valence3_opensubdiv_face_loop.py",
    ]
    assert all("cuda" not in path.as_posix().lower() for path in phase3_paths)
