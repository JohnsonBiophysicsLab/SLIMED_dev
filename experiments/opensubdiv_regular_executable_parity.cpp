#include "energy_force/Energy.hpp"
#include "energy_force/Energy_force_evaluator.hpp"
#include "energy_force/Force.hpp"
#include "mesh/Mesh.hpp"
#include "mesh/OpenSubdiv_regular_evaluator.hpp"

#include <cmath>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace
{
class ScopedCoutSilencer
{
  public:
    ScopedCoutSilencer() : original_(std::cout.rdbuf(buffer_.rdbuf())) {}
    ~ScopedCoutSilencer() { std::cout.rdbuf(original_); }

  private:
    std::ostringstream buffer_;
    std::streambuf *original_;
};

bool env_enabled(const char *name)
{
    const char *value = std::getenv(name);
    if (value == nullptr || value[0] == '\0')
    {
        return false;
    }
    const std::string text(value);
    return text != "0" && text != "false" && text != "FALSE" &&
           text != "off" && text != "OFF";
}

void append_matrix_column(std::vector<double> &values, const Matrix &matrix)
{
    for (int row = 0; row < matrix.nrow(); ++row)
    {
        values.push_back(matrix(row, 0));
    }
}

void append_energy(std::vector<double> &values, const Energy &energy)
{
    values.push_back(energy.energyCurvature);
    values.push_back(energy.energyArea);
    values.push_back(energy.energyVolume);
    values.push_back(energy.energyThickness);
    values.push_back(energy.energyTilt);
    values.push_back(energy.energyRegularization);
    values.push_back(energy.energyHarmonicBond);
    values.push_back(energy.energyGagScaffolding);
    values.push_back(energy.energyIdealizedProteinLattice);
    values.push_back(energy.energyTotal);
}

void append_force(std::vector<double> &values, const Force &force)
{
    append_matrix_column(values, force.forceCurvature);
    append_matrix_column(values, force.forceArea);
    append_matrix_column(values, force.forceVolume);
    append_matrix_column(values, force.forceThickness);
    append_matrix_column(values, force.forceTilt);
    append_matrix_column(values, force.forceRegularization);
    append_matrix_column(values, force.forceHarmonicBond);
    append_matrix_column(values, force.forceTotal);
}

void print_double_array(const std::vector<double> &values)
{
    std::cout << '[';
    for (std::size_t index = 0; index < values.size(); ++index)
    {
        if (index != 0)
        {
            std::cout << ',';
        }
        std::cout << values[index];
    }
    std::cout << ']';
}

void print_int_array(const std::vector<int> &values)
{
    std::cout << '[';
    for (std::size_t index = 0; index < values.size(); ++index)
    {
        if (index != 0)
        {
            std::cout << ',';
        }
        std::cout << values[index];
    }
    std::cout << ']';
}

bool all_finite(const std::vector<double> &values)
{
    for (double value : values)
    {
        if (!std::isfinite(value))
        {
            return false;
        }
    }
    return true;
}

struct Snapshot
{
    std::vector<double> globalEnergy;
    std::vector<double> faceEnergy;
    std::vector<double> vertexForces;
    std::vector<double> faceNormals;
    std::vector<double> faceArea;
    std::vector<double> faceLegacyVolume;
    std::vector<double> faceMeanCurvature;
    std::vector<int> activeFaceIds;
    int candidateShapeFaceCount = 0;
    int vertexCount = 0;
    bool finite = true;
};

Snapshot run_snapshot()
{
    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Periodic;
    param.sideX = 40.0;
    param.sideY = 10.0 * std::sqrt(3.0) / 2.0 * param.lFace;
    param.kCurv = 47.5;
    param.uSurf = 130.0;
    param.uVol = 65.0;
    param.area0 = 2.75;
    param.vol0 = 0.82;

    Mesh mesh(param);
    {
        ScopedCoutSilencer silence;
        mesh.setup_flat();
        mesh.calculate_element_area_volume();
        mesh.sum_membrane_area_and_volume(mesh.param.area0, mesh.param.vol0);
        mesh.update_previous_coord_for_vertex();
        mesh.update_reference_coord_from_previous_coord();
    }
    mesh.param.area0 = 2.75;
    mesh.param.vol0 = 0.82;
    for (Vertex &vertex : mesh.vertices)
    {
        const double index = static_cast<double>(vertex.index);
        vertex.coord.set(2,
                         0,
                         0.03 * std::sin(0.7 * index) +
                             0.01 * std::cos(0.3 * index));
    }

    const std::vector<std::vector<Matrix>> candidateRows =
        build_opensubdiv_regular_shape_functions_by_face(mesh);
    Snapshot snapshot;
    for (const std::vector<Matrix> &faceRows : candidateRows)
    {
        if (!faceRows.empty())
        {
            ++snapshot.candidateShapeFaceCount;
        }
    }

    {
        ScopedCoutSilencer silence;
        evaluate_energy_force(mesh);
    }

    append_energy(snapshot.globalEnergy, mesh.param.energy);
    snapshot.vertexCount = static_cast<int>(mesh.vertices.size());
    for (const Vertex &vertex : mesh.vertices)
    {
        append_force(snapshot.vertexForces, vertex.force);
    }
    for (const Face &face : mesh.faces)
    {
        if (face.isGhost || face.isBoundary ||
            face.oneRingVertices.size() != 12)
        {
            continue;
        }
        snapshot.activeFaceIds.push_back(face.index);
        append_energy(snapshot.faceEnergy, face.energy);
        append_matrix_column(snapshot.faceNormals, face.normVector);
        snapshot.faceArea.push_back(face.elementArea);
        snapshot.faceLegacyVolume.push_back(face.elementVolume);
        snapshot.faceMeanCurvature.push_back(face.meanCurvature);
    }
    snapshot.finite =
        all_finite(snapshot.globalEnergy) &&
        all_finite(snapshot.faceEnergy) &&
        all_finite(snapshot.vertexForces) &&
        all_finite(snapshot.faceNormals) &&
        all_finite(snapshot.faceArea) &&
        all_finite(snapshot.faceLegacyVolume) &&
        all_finite(snapshot.faceMeanCurvature);
    return snapshot;
}
} // namespace

int main()
{
    const bool candidateRequested =
        env_enabled("SLIMED_USE_OPENSUBDIV_REGULAR");
    const Snapshot snapshot = run_snapshot();
    const bool candidateInstalled =
        candidateRequested && snapshot.candidateShapeFaceCount > 0;
    const bool modeValid = candidateRequested == candidateInstalled;

    std::cout << std::setprecision(17);
    std::cout << '{';
#ifdef OMP
    std::cout << "\"execution_mode\":\"openmp\",";
#else
    std::cout << "\"execution_mode\":\"serial\",";
#endif
    std::cout << "\"candidate_rows_requested\":"
              << (candidateRequested ? "true" : "false") << ',';
    std::cout << "\"candidate_rows_installed_in_diagnostic_build\":"
              << (candidateInstalled ? "true" : "false") << ',';
    std::cout << "\"candidate_shape_face_count\":"
              << snapshot.candidateShapeFaceCount << ',';
    std::cout << "\"not_production_routing\":true,";
    std::cout << "\"finite\":" << (snapshot.finite ? "true" : "false") << ',';
    std::cout << "\"vertex_count\":" << snapshot.vertexCount << ',';
    std::cout << "\"active_face_ids\":";
    print_int_array(snapshot.activeFaceIds);
    std::cout << ",\"global_energy\":";
    print_double_array(snapshot.globalEnergy);
    std::cout << ",\"face_energy\":";
    print_double_array(snapshot.faceEnergy);
    std::cout << ",\"vertex_forces\":";
    print_double_array(snapshot.vertexForces);
    std::cout << ",\"face_normals\":";
    print_double_array(snapshot.faceNormals);
    std::cout << ",\"face_area\":";
    print_double_array(snapshot.faceArea);
    std::cout << ",\"face_legacy_volume\":";
    print_double_array(snapshot.faceLegacyVolume);
    std::cout << ",\"face_mean_curvature\":";
    print_double_array(snapshot.faceMeanCurvature);
    std::cout << '}';
    std::cout << '\n';
    return snapshot.finite && modeValid ? 0 : 1;
}
