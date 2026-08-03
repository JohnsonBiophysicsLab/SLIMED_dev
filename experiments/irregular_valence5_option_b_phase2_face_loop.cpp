#include "energy_force/Valence5_opensubdiv_face_loop.hpp"
#include "io/io.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
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

class ScopedCoutSilencer
{
public:
    ScopedCoutSilencer() : previous_(std::cout.rdbuf(buffer_.rdbuf())) {}
    ~ScopedCoutSilencer() { std::cout.rdbuf(previous_); }

private:
    std::ostringstream buffer_;
    std::streambuf *previous_;
};

std::array<const Matrix *, 8> force_terms(const Force &force)
{
    return {{
        &force.forceCurvature,
        &force.forceArea,
        &force.forceVolume,
        &force.forceThickness,
        &force.forceTilt,
        &force.forceRegularization,
        &force.forceHarmonicBond,
        &force.forceTotal,
    }};
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
    std::vector<double> values{
        mesh.param.area,
        mesh.param.vol,
    };
    const auto globalEnergy = energy_values(mesh.param.energy);
    values.insert(values.end(), globalEnergy.begin(), globalEnergy.end());
    for (const Vertex &vertex : mesh.vertices)
    {
        append_matrix(values, vertex.coord);
        append_matrix(values, vertex.coordRef);
        for (const Matrix *force : force_terms(vertex.force))
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
    std::vector<std::vector<int>> rings;
    rings.reserve(mesh.faces.size());
    for (const Face &face : mesh.faces)
        rings.push_back(face.oneRingVertices);
    return rings;
}

void configure_scientific_fixture(Mesh &mesh,
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

std::vector<double> aggregate_membrane_forces(const Mesh &mesh)
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
    double maximum = 0.0;
    for (std::size_t index = 0; index < left.size(); ++index)
        maximum = std::max(maximum, std::abs(left[index] - right[index]));
    return maximum;
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

bool write_long_double_oracle_package(
    const std::string &path,
    const Mesh &mesh,
    const slimed::opensubdiv_valence5_phase2::Valence5Phase2Result &result)
{
    if (mesh.vertices.size() != 12u || mesh.faces.size() != 20u ||
        result.rowProvider.rows.size() != mesh.faces.size())
        return false;
    std::ofstream output(path);
    if (!output)
        return false;
    output << std::setprecision(17) << "20 3 7 12\n"
           << "PARAMETERS " << mesh.param.kCurv << ' ' << 0.0 << ' '
           << mesh.param.uSurf << ' ' << mesh.param.area0 << ' '
           << mesh.param.uVol << ' ' << mesh.param.vol0 << ' '
           << result.totalArea << ' ' << result.totalVolume << '\n'
           << "REGULARIZATION";
    for (const Face &face : mesh.faces)
        output << ' ' << face.energy.energyRegularization;
    output << "\nCOORDINATES 12\n";
    for (const Vertex &vertex : mesh.vertices)
    {
        output << vertex.index;
        for (int axis = 0; axis < kAxes; ++axis)
            output << ' ' << vertex.coord.get(axis, 0);
        output << '\n';
    }
    constexpr double samples[3][3] = {
        {1.0 / 6.0, 1.0 / 6.0, 1.0 / 3.0},
        {1.0 / 6.0, 4.0 / 6.0, 1.0 / 3.0},
        {4.0 / 6.0, 1.0 / 6.0, 1.0 / 3.0},
    };
    for (std::size_t faceIndex = 0;
         faceIndex < result.rowProvider.rows.size();
         ++faceIndex)
    {
        const auto &faceRows = result.rowProvider.rows[faceIndex];
        output << "FACE " << faceIndex << ' ' << faceIndex;
        for (const int source : faceRows.orientedFaceVertices)
            output << ' ' << source;
        output << '\n';
        for (int sample = 0; sample < 3; ++sample)
        {
            output << "SAMPLE " << sample << ' ' << samples[sample][0]
                   << ' ' << samples[sample][1] << ' ' << samples[sample][2]
                   << '\n';
            for (int rowIndex = 0;
                 rowIndex < slimed::source_keyed_kernel::kDerivativeRowCount;
                 ++rowIndex)
            {
                std::array<double, 12> dense{};
                const auto &row = faceRows.samples[sample].rows[rowIndex];
                for (std::size_t source = 0; source < row.sourceIds.size(); ++source)
                    dense[row.sourceIds[source]] = row.coefficients[source];
                output << "ROW " << rowIndex;
                for (const double coefficient : dense)
                    output << ' ' << coefficient;
                output << '\n';
            }
        }
    }
    return static_cast<bool>(output);
}
} // namespace

int main(int argc, char **argv)
{
    if (argc != 6)
    {
        std::cerr << "usage: phase2_face_loop VERTICES FACES ENERGY_CSV CHECKPOINT ORACLE_PACKAGE\n";
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
    configure_scientific_fixture(mesh, vertices, faces);

    const std::vector<double> initial = mesh_state(mesh);
    const auto initialOneRings = one_rings(mesh);
    unsetenv("SLIMED_USE_OPENSUBDIV_VALENCE5_PHASE2");
    const auto missingExplicit =
        slimed::opensubdiv_valence5_phase2::
            evaluate_guarded_valence5_phase2_face_loop(mesh, {});
    slimed::opensubdiv_valence5_phase2::Valence5Phase2Request request;
    request.reviewerApprovedExplicitRequest = true;
    const auto missingRuntime =
        slimed::opensubdiv_valence5_phase2::
            evaluate_guarded_valence5_phase2_face_loop(mesh, request);
    const bool rejectionsAtomic =
        mesh_state(mesh) == initial && !missingExplicit.accepted &&
        !missingRuntime.accepted;

    setenv("SLIMED_USE_OPENSUBDIV_VALENCE5_PHASE2", "1", 1);
    const auto result =
        slimed::opensubdiv_valence5_phase2::
            evaluate_guarded_valence5_phase2_face_loop(mesh, request);

    if (!result.rowProvider.opensubdivCompiled)
    {
        const bool dependencyDisabled = rejectionsAtomic &&
            !result.accepted && mesh_state(mesh) == initial &&
            !result.actualProductionForcePathExecuted &&
            !result.productionFaceLoopExecuted &&
            !result.productionRouteEnabled &&
            !result.defaultEvaluatorCaller &&
            !result.phase3ActivationAuthorized;
        std::cout << '{'
                  << "\"status\":\""
                  << (dependencyDisabled ? "passed" : "failed") << "\","
                  << "\"dependency_disabled_contract_passed\":"
                  << (dependencyDisabled ? "true" : "false") << ','
                  << "\"production_route_enabled\":false,"
                  << "\"default_evaluator_caller\":false,"
                  << "\"phase3_activation_authorized\":false}"
                  << '\n';
        return dependencyDisabled ? 0 : 1;
    }
    if (!result.accepted)
    {
        std::cout << "{\"status\":\"failed\",\"reason\":\""
                  << result.rejectionReason << "\"}\n";
        return 1;
    }
    const bool productionOneRingsPreserved =
        one_rings(mesh) == initialOneRings;

    // The inventory separately proves that Mesh::Compute_Energy_And_Force
    // contains no Phase 2 caller. These runtime flags bind the same boundary.
    const bool defaultCallerRemainedFallback =
        result.accepted && !result.productionRouteEnabled &&
        !result.defaultEvaluatorCaller && !result.phase3ActivationAuthorized;

    const auto globalEnergy = energy_values(mesh.param.energy);
    const auto faceEnergy = face_energy_values(mesh);
    const auto geometry = face_geometry_values(mesh);
    const auto forces = aggregate_membrane_forces(mesh);
    const bool oraclePackageWritten =
        write_long_double_oracle_package(argv[5], mesh, result);

    Record record(1);
    record.add(mesh.param.area,
               mesh.param.energy,
               mesh.calculate_mean_force());
    Model model(mesh, record);
    bool energyWriter = false;
    bool checkpointWriter = false;
    {
        ScopedCoutSilencer silence;
        energyWriter = write_energy_force_data_to_csv(model, argv[3]);
        write_element_face_energy_to_csv(model);
        checkpointWriter =
            write_model_restart_checkpoint(model, argv[4], 7);
    }
    const bool faceWriter =
        std::filesystem::exists("ElementFaceEnergy.csv");

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
    const double restartEnergyDifference = checkpointLoader
        && !restartRecord.energyVec.empty()
        ? maximum_difference(globalEnergy,
                             energy_values(restartRecord.energyVec.front()))
        : INFINITY;
    const double restartFaceEnergyDifference = checkpointLoader
        ? maximum_difference(faceEnergy,
                             face_energy_values(restartMesh))
        : INFINITY;
    const double restartGeometryDifference = checkpointLoader
        ? maximum_difference(geometry,
                             face_geometry_values(restartMesh))
        : INFINITY;
    const double restartForceDifference = checkpointLoader
        ? maximum_difference(forces,
                             aggregate_membrane_forces(restartMesh))
        : INFINITY;

    const bool passed = rejectionsAtomic && result.accepted &&
        result.actualProductionForcePathExecuted &&
        result.productionFaceLoopExecuted &&
        result.completeTransactionValidatedBeforeMutation &&
        result.outputStateFinite && result.faceObservablesMatchDryRun &&
        result.sourceForcesMatchDryRun &&
        productionOneRingsPreserved &&
        !result.productionRouteEnabled && !result.defaultEvaluatorCaller &&
        !result.phase3ActivationAuthorized &&
        defaultCallerRemainedFallback && energyWriter && faceWriter &&
        oraclePackageWritten &&
        checkpointWriter && checkpointLoader &&
        restartEnergyDifference == 0.0 &&
        restartFaceEnergyDifference == 0.0 &&
        restartGeometryDifference == 0.0 &&
        restartForceDifference == 0.0;

    std::cout << std::setprecision(17) << '{'
              << "\"status\":\"" << (passed ? "passed" : "failed") << "\",";
    std::cout << "\"explicit_gate_rejection_atomic\":"
              << (rejectionsAtomic ? "true" : "false") << ','
              << "\"dependency_compiled\":"
              << (result.rowProvider.opensubdivCompiled ? "true" : "false") << ','
              << "\"runtime_opt_in_requested\":"
              << (result.runtimeOptInRequested ? "true" : "false") << ','
              << "\"production_force_path_executed\":"
              << (result.actualProductionForcePathExecuted ? "true" : "false") << ','
              << "\"production_face_loop_executed\":"
              << (result.productionFaceLoopExecuted ? "true" : "false") << ','
              << "\"production_one_rings_preserved\":"
              << (productionOneRingsPreserved ? "true" : "false") << ','
              << "\"production_route_enabled\":false,"
              << "\"default_evaluator_caller\":false,"
              << "\"phase3_activation_authorized\":false,"
              << "\"default_caller_remained_fallback\":"
              << (defaultCallerRemainedFallback ? "true" : "false") << ','
              << "\"face_observable_dry_run_max_abs_difference\":"
              << result.maxFaceObservableDifference << ','
              << "\"source_force_dry_run_max_abs_difference\":"
              << result.maxSourceForceDifference << ','
              << "\"output_state_finite\":"
              << (result.outputStateFinite ? "true" : "false") << ','
              << "\"long_double_oracle_package_written\":"
              << (oraclePackageWritten ? "true" : "false") << ','
              << "\"energy_force_writer_executed\":"
              << (energyWriter ? "true" : "false") << ','
              << "\"element_face_energy_writer_executed\":"
              << (faceWriter ? "true" : "false") << ','
              << "\"checkpoint_writer_executed\":"
              << (checkpointWriter ? "true" : "false") << ','
              << "\"checkpoint_loader_executed\":"
              << (checkpointLoader ? "true" : "false") << ','
              << "\"checkpoint_global_energy_max_abs_difference\":"
              << restartEnergyDifference << ','
              << "\"checkpoint_face_energy_max_abs_difference\":"
              << restartFaceEnergyDifference << ','
              << "\"checkpoint_geometry_max_abs_difference\":"
              << restartGeometryDifference << ','
              << "\"checkpoint_membrane_force_max_abs_difference\":"
              << restartForceDifference << ','
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
