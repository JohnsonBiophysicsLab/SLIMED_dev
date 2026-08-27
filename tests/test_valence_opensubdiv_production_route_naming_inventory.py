from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_valence3_valence4_and_valence5_expose_canonical_route_vocabulary():
    caller = (
        ROOT / "src/energy_force/Compute_energy_and_force_on_mesh.cpp"
    ).read_text()
    valence5_header = (
        ROOT / "include/energy_force/Valence5_opensubdiv_face_loop.hpp"
    ).read_text()
    valence5_source = (
        ROOT / "src/energy_force/Valence5_opensubdiv_face_loop.cpp"
    ).read_text()
    valence3_header = (
        ROOT / "include/energy_force/Valence3_opensubdiv_production_route.hpp"
    ).read_text()

    assert "Valence4_opensubdiv_production_route.hpp" in caller
    assert "Valence5_opensubdiv_production_route.hpp" in caller
    assert "Valence3_opensubdiv_production_route.hpp" in caller
    assert "Valence3_opensubdiv_face_loop.hpp" in valence3_header
    assert "evaluate_guarded_valence4_opensubdiv_production_route(*this)" in caller
    assert "evaluate_guarded_valence5_opensubdiv_production_route(*this)" in caller
    assert "evaluate_guarded_valence5_opensubdiv_production_route" in valence5_header
    assert "evaluate_guarded_valence5_production_route" in valence5_header
    assert (
        "return evaluate_guarded_valence5_opensubdiv_production_route(mesh);"
        in valence5_source
    )


def test_old_implementation_headers_remain_as_compatibility_surfaces():
    v4 = (
        ROOT / "include/energy_force/Valence4_opensubdiv_production_route.hpp"
    ).read_text()
    v5 = (
        ROOT / "include/energy_force/Valence5_opensubdiv_production_route.hpp"
    ).read_text()
    assert "Valence4_face_loop_route_preflight.hpp" in v4
    assert "Valence5_opensubdiv_face_loop.hpp" in v5
