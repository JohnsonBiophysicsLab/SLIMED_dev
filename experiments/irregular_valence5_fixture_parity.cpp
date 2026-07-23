#include "energy_force/Energy.hpp"
#include "energy_force/Energy_force_evaluator.hpp"
#include "energy_force/Force.hpp"
#include "io/io.hpp"
#include "mesh/Mesh.hpp"

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <set>
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
    return std::all_of(values.begin(), values.end(), [](const double value) {
        return std::isfinite(value);
    });
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
    std::vector<int> oneRingSourceIds;
    int vertexCount = 0;
    int faceCount = 0;
    int elevenControlFaceCount = 0;
    bool allValenceFive = true;
    bool allPhysical = true;
    bool duplicateAggregationShape = true;
    bool finite = true;
    bool nonzeroForce = false;
};

Snapshot run_snapshot()
{
    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Fixed;
    param.subDivideTimes = 2;
    param.kCurv = 47.5;
    param.uSurf = 130.0;
    param.uVol = 65.0;

    const auto verticesData = read_data_from_csv<double>(
        "data/fixtures/closed_valence5/vertices.csv");
    const auto facesData = read_data_from_csv<int>(
        "data/fixtures/closed_valence5/faces.csv");

    Mesh mesh(param);
    {
        ScopedCoutSilencer silence;
        mesh.setup_from_vertices_faces(verticesData, facesData);
    }

    for (Vertex &vertex : mesh.vertices)
    {
        const double index = static_cast<double>(vertex.index + 1);
        vertex.coord.set(0, 0, vertex.coord(0, 0) + 0.017 * std::sin(0.37 * index));
        vertex.coord.set(1, 0, vertex.coord(1, 0) - 0.013 * std::cos(0.29 * index));
        vertex.coord.set(2, 0, vertex.coord(2, 0) + 0.019 * std::sin(0.41 * index));
    }
    mesh.update_previous_coord_for_vertex();
    mesh.update_reference_coord_from_previous_coord();

    {
        ScopedCoutSilencer silence;
        mesh.calculate_element_area_volume();
        mesh.sum_membrane_area_and_volume(mesh.param.area, mesh.param.vol);
    }
    mesh.param.area0 = 0.91 * mesh.param.area;
    mesh.param.vol0 = 0.93 * mesh.param.vol;

    Snapshot snapshot;
    snapshot.vertexCount = static_cast<int>(mesh.vertices.size());
    snapshot.faceCount = static_cast<int>(mesh.faces.size());
    for (const Vertex &vertex : mesh.vertices)
    {
        snapshot.allValenceFive =
            snapshot.allValenceFive && vertex.adjacentVertices.size() == 5;
    }
    for (const Face &face : mesh.faces)
    {
        snapshot.allPhysical =
            snapshot.allPhysical && !face.isGhost && !face.isBoundary;
        if (face.oneRingVertices.size() == 11)
        {
            ++snapshot.elevenControlFaceCount;
        }
        const std::set<int> uniqueSources(face.oneRingVertices.begin(),
                                          face.oneRingVertices.end());
        snapshot.duplicateAggregationShape =
            snapshot.duplicateAggregationShape &&
            face.oneRingVertices.size() == 11 && uniqueSources.size() == 9;
        snapshot.oneRingSourceIds.insert(snapshot.oneRingSourceIds.end(),
                                         face.oneRingVertices.begin(),
                                         face.oneRingVertices.end());
    }

    {
        ScopedCoutSilencer silence;
        evaluate_energy_force(mesh);
    }

    append_energy(snapshot.globalEnergy, mesh.param.energy);
    for (const Vertex &vertex : mesh.vertices)
    {
        append_force(snapshot.vertexForces, vertex.force);
    }
    for (const Face &face : mesh.faces)
    {
        if (face.isGhost || face.isBoundary || face.oneRingVertices.size() != 11)
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
    snapshot.nonzeroForce = std::any_of(
        snapshot.vertexForces.begin(), snapshot.vertexForces.end(),
        [](const double value) { return std::abs(value) > 1.0e-12; });
    return snapshot;
}
} // namespace

int main()
{
    const Snapshot snapshot = run_snapshot();
    const bool topologyValid =
        snapshot.vertexCount == 12 && snapshot.faceCount == 20 &&
        snapshot.elevenControlFaceCount == 20 && snapshot.allValenceFive &&
        snapshot.allPhysical && snapshot.duplicateAggregationShape;

    std::cout << std::setprecision(17);
    std::cout << '{';
#ifdef OMP
    std::cout << "\"execution_mode\":\"openmp\",";
#else
    std::cout << "\"execution_mode\":\"serial\",";
#endif
    std::cout << "\"fixture\":\"closed_valence5_icosahedron\",";
    std::cout << "\"scientific_stand_in_scope\":\"narrow_positive_depth_11_control\",";
    std::cout << "\"not_broader_valence_routing\":true,";
    std::cout << "\"vertex_count\":" << snapshot.vertexCount << ',';
    std::cout << "\"face_count\":" << snapshot.faceCount << ',';
    std::cout << "\"eleven_control_face_count\":"
              << snapshot.elevenControlFaceCount << ',';
    std::cout << "\"all_valence_five\":"
              << (snapshot.allValenceFive ? "true" : "false") << ',';
    std::cout << "\"all_faces_physical\":"
              << (snapshot.allPhysical ? "true" : "false") << ',';
    std::cout << "\"deterministic_duplicate_aggregation_shape\":"
              << (snapshot.duplicateAggregationShape ? "true" : "false") << ',';
    std::cout << "\"finite\":" << (snapshot.finite ? "true" : "false") << ',';
    std::cout << "\"nonzero_force\":"
              << (snapshot.nonzeroForce ? "true" : "false") << ',';
    std::cout << "\"active_face_ids\":";
    print_int_array(snapshot.activeFaceIds);
    std::cout << ",\"one_ring_source_ids\":";
    print_int_array(snapshot.oneRingSourceIds);
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
    return topologyValid && snapshot.finite && snapshot.nonzeroForce ? 0 : 1;
}
