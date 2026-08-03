#include "energy_force/Valence5_opensubdiv_face_loop.hpp"
#include "io/io.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace
{
constexpr int kEnergyChannels = 10;
constexpr int kForceKinds = 3;
constexpr int kAxes = 3;
constexpr double kTolerance = 1.0e-10;

class ScopedCoutSilencer
{
public:
    ScopedCoutSilencer() : previous_(std::cout.rdbuf(buffer_.rdbuf())) {}
    ~ScopedCoutSilencer() { std::cout.rdbuf(previous_); }

private:
    std::ostringstream buffer_;
    std::streambuf *previous_;
};

bool env_enabled(const char *name)
{
    const char *value = std::getenv(name);
    return value != nullptr && std::string(value) == "1";
}

std::vector<double> energy_values(const Energy &energy)
{
    return {
        energy.energyCurvature,
        energy.energyArea,
        energy.energyVolume,
        energy.energyThickness,
        energy.energyTilt,
        energy.energyRegularization,
        energy.energyHarmonicBond,
        energy.energyGagScaffolding,
        energy.energyIdealizedProteinLattice,
        energy.energyTotal,
    };
}

void append_matrix(std::vector<double> &values, const Matrix &matrix)
{
    values.push_back(matrix.mat == nullptr ? 0.0 : 1.0);
    if (matrix.mat == nullptr)
        return;
    for (int row = 0; row < matrix.nrow(); ++row)
        for (int column = 0; column < matrix.ncol(); ++column)
            values.push_back(matrix.get(row, column));
}

std::vector<double> mesh_state(const Mesh &mesh)
{
    std::vector<double> values{mesh.param.area, mesh.param.vol};
    const auto globalEnergy = energy_values(mesh.param.energy);
    values.insert(values.end(), globalEnergy.begin(), globalEnergy.end());
    for (const Vertex &vertex : mesh.vertices)
    {
        append_matrix(values, vertex.coord);
        append_matrix(values, vertex.coordRef);
        const std::array<const Matrix *, 8> forces{{
            &vertex.force.forceCurvature,
            &vertex.force.forceArea,
            &vertex.force.forceVolume,
            &vertex.force.forceThickness,
            &vertex.force.forceTilt,
            &vertex.force.forceRegularization,
            &vertex.force.forceHarmonicBond,
            &vertex.force.forceTotal,
        }};
        for (const Matrix *force : forces)
            append_matrix(values, *force);
    }
    for (const Face &face : mesh.faces)
    {
        values.push_back(face.elementArea);
        values.push_back(face.elementVolume);
        values.push_back(face.meanCurvature);
        append_matrix(values, face.normVector);
        const auto faceEnergy = energy_values(face.energy);
        values.insert(values.end(), faceEnergy.begin(), faceEnergy.end());
    }
    return values;
}

std::vector<std::vector<int>> one_rings(const Mesh &mesh)
{
    std::vector<std::vector<int>> result;
    result.reserve(mesh.faces.size());
    for (const Face &face : mesh.faces)
        result.push_back(face.oneRingVertices);
    return result;
}

void configure_fixture(Mesh &mesh,
                       const std::vector<std::vector<double>> &vertices,
                       const std::vector<std::vector<int>> &faces)
{
    mesh.setup_from_vertices_faces(vertices, faces);
    for (Vertex &vertex : mesh.vertices)
    {
        const double index = static_cast<double>(vertex.index + 1);
        vertex.coord.set(0, 0,
                         vertex.coord.get(0, 0) +
                             0.017 * std::sin(0.37 * index));
        vertex.coord.set(1, 0,
                         vertex.coord.get(1, 0) -
                             0.013 * std::cos(0.29 * index));
        vertex.coord.set(2, 0,
                         vertex.coord.get(2, 0) +
                             0.019 * std::sin(0.41 * index));
    }
    mesh.update_previous_coord_for_vertex();
    mesh.update_reference_coord_from_previous_coord();
    mesh.calculate_element_area_volume();
    mesh.sum_membrane_area_and_volume(mesh.param.area, mesh.param.vol);
    mesh.param.area0 = 0.91 * mesh.param.area;
    mesh.param.vol0 = 0.93 * mesh.param.vol;
}

std::vector<double> face_energy_values(const Mesh &mesh)
{
    std::vector<double> values;
    values.reserve(mesh.faces.size() * kEnergyChannels);
    for (const Face &face : mesh.faces)
    {
        const auto energy = energy_values(face.energy);
        values.insert(values.end(), energy.begin(), energy.end());
    }
    return values;
}

std::vector<double> face_geometry_values(const Mesh &mesh)
{
    std::vector<double> values;
    values.reserve(mesh.faces.size() * 6u);
    for (const Face &face : mesh.faces)
    {
        for (int axis = 0; axis < kAxes; ++axis)
            values.push_back(face.normVector.get(axis, 0));
        values.push_back(face.meanCurvature);
        values.push_back(face.elementArea);
        values.push_back(face.elementVolume);
    }
    return values;
}

std::vector<double> membrane_force_values(const Mesh &mesh)
{
    std::vector<double> values;
    values.reserve(mesh.vertices.size() * kForceKinds * kAxes);
    for (const Vertex &vertex : mesh.vertices)
    {
        const std::array<const Matrix *, kForceKinds> forces{{
            &vertex.force.forceCurvature,
            &vertex.force.forceArea,
            &vertex.force.forceVolume,
        }};
        for (const Matrix *force : forces)
            for (int axis = 0; axis < kAxes; ++axis)
                values.push_back(force->get(axis, 0));
    }
    return values;
}

double maximum_difference(const std::vector<double> &left,
                          const std::vector<double> &right)
{
    if (left.size() != right.size())
        return INFINITY;
    double result = 0.0;
    for (std::size_t index = 0; index < left.size(); ++index)
        result = std::max(result, std::abs(left[index] - right[index]));
    return result;
}

void print_values(const std::vector<double> &values)
{
    std::cout << '[';
    for (std::size_t index = 0; index < values.size(); ++index)
    {
        if (index)
            std::cout << ',';
        std::cout << values[index];
    }
    std::cout << ']';
}
} // namespace

int main(int argc, char **argv)
{
    if (argc != 5)
    {
        std::cerr << "usage: phase3_activation VERTICES FACES ENERGY_CSV CHECKPOINT\n";
        return 2;
    }
    const auto vertices = read_data_from_csv<double>(argv[1]);
    const auto faces = read_data_from_csv<int>(argv[2]);
    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Fixed;
    param.subDivideTimes = 2;
    param.kCurv = 47.5;
    param.uSurf = 130.0;
    param.uVol = 65.0;

    Mesh mesh(param);
    configure_fixture(mesh, vertices, faces);
    const auto initialState = mesh_state(mesh);
    const auto initialOneRings = one_rings(mesh);
    const bool valence5Requested =
        env_enabled("SLIMED_USE_OPENSUBDIV_VALENCE5");
    const bool valence4Requested =
        env_enabled("SLIMED_USE_OPENSUBDIV_VALENCE4");

    bool defaultCallerThrew = false;
    try
    {
        mesh.Compute_Energy_And_Force();
    }
    catch (const std::runtime_error &)
    {
        defaultCallerThrew = true;
    }

    if (valence4Requested && valence5Requested)
    {
        const bool passed = defaultCallerThrew && mesh_state(mesh) == initialState &&
            one_rings(mesh) == initialOneRings;
        std::cout << '{'
                  << "\"status\":\"" << (passed ? "passed" : "failed") << "\","
                  << "\"conflicting_route_request_rejected_atomically\":"
                  << (passed ? "true" : "false") << "}\n";
        return passed ? 0 : 1;
    }

    Mesh directMesh(param);
    configure_fixture(directMesh, vertices, faces);
    const auto directInitialState = mesh_state(directMesh);
    const auto directInitialOneRings = one_rings(directMesh);
    const auto direct = slimed::opensubdiv_valence5_phase2::
        evaluate_guarded_valence5_opensubdiv_production_route(directMesh);

    if (!valence5Requested)
    {
        const bool passed = !defaultCallerThrew && !direct.accepted &&
            mesh_state(directMesh) == directInitialState &&
            one_rings(directMesh) == directInitialOneRings;
        const auto globalEnergy = energy_values(mesh.param.energy);
        const auto faceEnergy = face_energy_values(mesh);
        const auto geometry = face_geometry_values(mesh);
        const auto forces = membrane_force_values(mesh);
        std::cout << std::setprecision(17) << '{'
                  << "\"status\":\"" << (passed ? "passed" : "failed") << "\","
                  << "\"fallback_preserved\":" << (passed ? "true" : "false") << ','
                  << "\"production_route_enabled\":false,"
                  << "\"default_evaluator_caller\":false,"
                  << "\"phase3_activation_authorized\":false,"
                  << "\"global_energy\":";
        print_values(globalEnergy);
        std::cout << ",\"face_energy\":";
        print_values(faceEnergy);
        std::cout << ",\"face_geometry\":";
        print_values(geometry);
        std::cout << ",\"aggregate_source_forces\":";
        print_values(forces);
        std::cout << "}\n";
        return passed ? 0 : 1;
    }

    if (!direct.rowProvider.opensubdivCompiled)
    {
        const bool passed = defaultCallerThrew && !direct.accepted &&
            mesh_state(mesh) == initialState &&
            mesh_state(directMesh) == directInitialState &&
            one_rings(mesh) == initialOneRings &&
            one_rings(directMesh) == directInitialOneRings;
        std::cout << '{'
                  << "\"status\":\"" << (passed ? "passed" : "failed") << "\","
                  << "\"dependency_absent_request_rejected_atomically\":"
                  << (passed ? "true" : "false") << ','
                  << "\"production_route_enabled\":false,"
                  << "\"default_evaluator_caller\":false,"
                  << "\"phase3_activation_authorized\":false}\n";
        return passed ? 0 : 1;
    }

    const auto globalEnergy = energy_values(mesh.param.energy);
    const auto faceEnergy = face_energy_values(mesh);
    const auto geometry = face_geometry_values(mesh);
    const auto forces = membrane_force_values(mesh);
    const double globalCallerDifference = maximum_difference(
        globalEnergy, energy_values(directMesh.param.energy));
    const double faceCallerDifference = maximum_difference(
        faceEnergy, face_energy_values(directMesh));
    const double geometryCallerDifference = maximum_difference(
        geometry, face_geometry_values(directMesh));
    const double forceCallerDifference = maximum_difference(
        forces, membrane_force_values(directMesh));
    const bool oneRingsPreserved = one_rings(mesh) == initialOneRings &&
        one_rings(directMesh) == directInitialOneRings;

    Record record(1);
    record.add(mesh.param.area, mesh.param.energy, mesh.calculate_mean_force());
    Model model(mesh, record);
    bool energyWriter = false;
    bool checkpointWriter = false;
    {
        ScopedCoutSilencer silence;
        energyWriter = write_energy_force_data_to_csv(model, argv[3]);
        write_element_face_energy_to_csv(model);
        checkpointWriter = write_model_restart_checkpoint(model, argv[4], 11);
    }
    const bool faceWriter = std::filesystem::exists("ElementFaceEnergy.csv");

    Param restartParam;
    restartParam.VERBOSE_MODE = false;
    restartParam.boundaryCondition = BoundaryType::Fixed;
    restartParam.subDivideTimes = 2;
    Mesh restartMesh(restartParam);
    restartMesh.setup_from_vertices_faces(vertices, faces);
    restartMesh.update_previous_coord_for_vertex();
    restartMesh.update_reference_coord_from_previous_coord();
    Record restartRecord(1);
    Model restartModel(restartMesh, restartRecord);
    bool checkpointLoader = false;
    {
        ScopedCoutSilencer silence;
        checkpointLoader = checkpointWriter &&
            load_model_restart_checkpoint(restartModel, argv[4]);
    }
    const double restartEnergyDifference = checkpointLoader &&
            !restartRecord.energyVec.empty()
        ? maximum_difference(
              globalEnergy, energy_values(restartRecord.energyVec.front()))
        : INFINITY;
    const double restartFaceDifference = checkpointLoader
        ? maximum_difference(faceEnergy, face_energy_values(restartMesh))
        : INFINITY;
    const double restartGeometryDifference = checkpointLoader
        ? maximum_difference(geometry, face_geometry_values(restartMesh))
        : INFINITY;
    const double restartForceDifference = checkpointLoader
        ? maximum_difference(forces, membrane_force_values(restartMesh))
        : INFINITY;

    const bool passed = !defaultCallerThrew && direct.accepted &&
        direct.productionRouteEnabled && direct.defaultEvaluatorCaller &&
        direct.phase3ActivationAuthorized &&
        direct.actualProductionForcePathExecuted &&
        direct.completeTransactionValidatedBeforeMutation &&
        oneRingsPreserved &&
        globalCallerDifference <= kTolerance &&
        faceCallerDifference <= kTolerance &&
        geometryCallerDifference <= kTolerance &&
        forceCallerDifference <= kTolerance &&
        energyWriter && faceWriter && checkpointWriter && checkpointLoader &&
        restartEnergyDifference == 0.0 && restartFaceDifference == 0.0 &&
        restartGeometryDifference == 0.0 && restartForceDifference == 0.0;

    std::cout << std::setprecision(17) << '{'
              << "\"status\":\"" << (passed ? "passed" : "failed") << "\","
              << "\"production_route_enabled\":"
              << (direct.productionRouteEnabled ? "true" : "false") << ','
              << "\"default_evaluator_caller\":"
              << (direct.defaultEvaluatorCaller ? "true" : "false") << ','
              << "\"phase3_activation_authorized\":"
              << (direct.phase3ActivationAuthorized ? "true" : "false") << ','
              << "\"production_force_path_executed\":"
              << (direct.actualProductionForcePathExecuted ? "true" : "false") << ','
              << "\"production_one_rings_preserved\":"
              << (oneRingsPreserved ? "true" : "false") << ','
              << "\"default_vs_direct_global_max_abs_difference\":"
              << globalCallerDifference << ','
              << "\"default_vs_direct_face_max_abs_difference\":"
              << faceCallerDifference << ','
              << "\"default_vs_direct_geometry_max_abs_difference\":"
              << geometryCallerDifference << ','
              << "\"default_vs_direct_force_max_abs_difference\":"
              << forceCallerDifference << ','
              << "\"energy_force_writer_executed\":"
              << (energyWriter ? "true" : "false") << ','
              << "\"element_face_energy_writer_executed\":"
              << (faceWriter ? "true" : "false") << ','
              << "\"checkpoint_roundtrip_exact\":"
              << ((restartEnergyDifference == 0.0 &&
                   restartFaceDifference == 0.0 &&
                   restartGeometryDifference == 0.0 &&
                   restartForceDifference == 0.0) ? "true" : "false") << ','
              << "\"global_energy\":";
    print_values(globalEnergy);
    std::cout << ",\"face_energy\":";
    print_values(faceEnergy);
    std::cout << ",\"face_geometry\":";
    print_values(geometry);
    std::cout << ",\"aggregate_source_forces\":";
    print_values(forces);
    std::cout << "}\n";
    return passed ? 0 : 1;
}
