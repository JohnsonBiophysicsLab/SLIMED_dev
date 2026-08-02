#include "io/io.hpp"

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

namespace
{
constexpr int kVertexCount = 12;
constexpr int kFaceCount = 20;
constexpr int kEnergyChannels = 10;
constexpr int kGeometryChannels = 6;
constexpr int kForceKinds = 3;
constexpr int kAxes = 3;

bool finite_value(const double value)
{
    return std::isfinite(value);
}

bool read_tag(std::istream &input, const char *expected)
{
    std::string actual;
    return static_cast<bool>(input >> actual) && actual == expected;
}

bool read_values(std::istream &input, std::vector<double> &values,
                 const std::size_t count)
{
    values.resize(count);
    for (double &value : values)
    {
        if (!(input >> value) || !finite_value(value))
            return false;
    }
    return true;
}

void assign_energy(Energy &energy, const std::vector<double> &values,
                   const std::size_t offset)
{
    energy.energyCurvature = values[offset];
    energy.energyArea = values[offset + 1];
    energy.energyVolume = values[offset + 2];
    energy.energyThickness = values[offset + 3];
    energy.energyTilt = values[offset + 4];
    energy.energyRegularization = values[offset + 5];
    energy.energyHarmonicBond = values[offset + 6];
    energy.energyGagScaffolding = values[offset + 7];
    energy.energyIdealizedProteinLattice = values[offset + 8];
    energy.energyTotal = values[offset + 9];
}

double energy_delta(const Energy &left, const Energy &right)
{
    const double values[][2] = {
        {left.energyCurvature, right.energyCurvature},
        {left.energyArea, right.energyArea},
        {left.energyVolume, right.energyVolume},
        {left.energyThickness, right.energyThickness},
        {left.energyTilt, right.energyTilt},
        {left.energyRegularization, right.energyRegularization},
        {left.energyHarmonicBond, right.energyHarmonicBond},
        {left.energyGagScaffolding, right.energyGagScaffolding},
        {left.energyIdealizedProteinLattice,
         right.energyIdealizedProteinLattice},
        {left.energyTotal, right.energyTotal},
    };
    double maximum = 0.0;
    for (const auto &pair : values)
        maximum = std::max(maximum, std::abs(pair[0] - pair[1]));
    return maximum;
}
} // namespace

int main(int argc, char **argv)
{
    if (argc != 4)
    {
        std::cerr << "usage: output_visibility PACKAGE ENERGY_CSV CHECKPOINT\n";
        return 2;
    }

    std::ifstream input(argv[1]);
    int vertexCount = 0;
    int faceCount = 0;
    if (!input || !read_tag(input, "COUNTS") ||
        !(input >> vertexCount >> faceCount) ||
        vertexCount != kVertexCount || faceCount != kFaceCount)
    {
        std::cerr << "invalid Option B output package counts\n";
        return 3;
    }

    std::vector<double> coordinates;
    std::vector<std::vector<int>> faces(kFaceCount, std::vector<int>(3));
    std::vector<double> globalEnergy;
    std::vector<double> faceEnergy;
    std::vector<double> geometry;
    std::vector<double> aggregateForces;
    if (!read_tag(input, "COORDINATES") ||
        !read_values(input, coordinates, kVertexCount * kAxes) ||
        !read_tag(input, "FACES"))
    {
        std::cerr << "invalid Option B output package geometry\n";
        return 3;
    }
    for (int face = 0; face < kFaceCount; ++face)
    {
        int index = -1;
        if (!(input >> index >> faces[face][0] >> faces[face][1] >>
              faces[face][2]) ||
            index != face)
        {
            std::cerr << "invalid Option B output face identity\n";
            return 3;
        }
    }
    if (!read_tag(input, "GLOBAL_ENERGY") ||
        !read_values(input, globalEnergy, kEnergyChannels) ||
        !read_tag(input, "FACE_ENERGY") ||
        !read_values(input, faceEnergy, kFaceCount * kEnergyChannels) ||
        !read_tag(input, "FACE_GEOMETRY") ||
        !read_values(input, geometry, kFaceCount * kGeometryChannels) ||
        !read_tag(input, "AGGREGATE_FORCES") ||
        !read_values(input, aggregateForces,
                     kVertexCount * kForceKinds * kAxes) ||
        !read_tag(input, "END"))
    {
        std::cerr << "invalid Option B output observable package\n";
        return 3;
    }
    input >> std::ws;
    if (input.peek() != std::char_traits<char>::eof())
    {
        std::cerr << "trailing Option B output package token\n";
        return 3;
    }

    std::vector<std::vector<double>> vertices(
        kVertexCount, std::vector<double>(kAxes));
    for (int vertex = 0; vertex < kVertexCount; ++vertex)
        for (int axis = 0; axis < kAxes; ++axis)
            vertices[vertex][axis] = coordinates[vertex * kAxes + axis];

    Param param;
    param.VERBOSE_MODE = false;
    Mesh mesh(param);
    mesh.setup_from_vertices_faces(vertices, faces);
    mesh.update_previous_coord_for_vertex();
    mesh.update_reference_coord_from_previous_coord();
    assign_energy(mesh.param.energy, globalEnergy, 0);

    for (int face = 0; face < kFaceCount; ++face)
    {
        Face &target = mesh.faces[face];
        assign_energy(target.energy, faceEnergy,
                      static_cast<std::size_t>(face) * kEnergyChannels);
        const std::size_t offset =
            static_cast<std::size_t>(face) * kGeometryChannels;
        target.normVector = mat_calloc(kAxes, 1);
        for (int axis = 0; axis < kAxes; ++axis)
            target.normVector.set(axis, 0, geometry[offset + axis]);
        target.meanCurvature = geometry[offset + 3];
        target.elementArea = geometry[offset + 4];
        target.elementVolume = geometry[offset + 5];
    }

    for (int vertex = 0; vertex < kVertexCount; ++vertex)
    {
        Force &force = mesh.vertices[vertex].force;
        Matrix *kinds[] = {
            &force.forceCurvature, &force.forceArea, &force.forceVolume};
        for (int kind = 0; kind < kForceKinds; ++kind)
            for (int axis = 0; axis < kAxes; ++axis)
                kinds[kind]->set(
                    axis, 0,
                    aggregateForces[vertex * kForceKinds * kAxes +
                                    kind * kAxes + axis]);
        force.calculate_total_force();
    }

    double totalArea = 0.0;
    for (const Face &face : mesh.faces)
        totalArea += face.elementArea;
    Record record(1);
    record.add(totalArea, mesh.param.energy, mesh.calculate_mean_force());
    Model model(mesh, record);

    const bool energyWriterPassed =
        write_energy_force_data_to_csv(model, argv[2]);
    write_element_face_energy_to_csv(model);
    const bool faceFileExists =
        std::filesystem::exists("ElementFaceEnergy.csv");
    const bool checkpointWriterPassed =
        write_model_restart_checkpoint(model, argv[3], 1);

    Param restartParam;
    restartParam.VERBOSE_MODE = false;
    Mesh restartMesh(restartParam);
    restartMesh.setup_from_vertices_faces(vertices, faces);
    restartMesh.update_previous_coord_for_vertex();
    restartMesh.update_reference_coord_from_previous_coord();
    Record restartRecord(1);
    Model restartModel(restartMesh, restartRecord);
    const bool checkpointLoadPassed = checkpointWriterPassed &&
        load_model_restart_checkpoint(restartModel, argv[3]);

    double forceRoundtripMaximum = 0.0;
    if (checkpointLoadPassed)
    {
        for (int vertex = 0; vertex < kVertexCount; ++vertex)
            for (int axis = 0; axis < kAxes; ++axis)
                forceRoundtripMaximum = std::max(
                    forceRoundtripMaximum,
                    std::abs(mesh.vertices[vertex].force.forceTotal(axis, 0) -
                             restartMesh.vertices[vertex].force.forceTotal(axis, 0)));
    }
    const double recordEnergyMaximum =
        checkpointLoadPassed && !restartRecord.energyVec.empty()
            ? energy_delta(record.energyVec[0], restartRecord.energyVec[0])
            : -1.0;

    double forceFamilyMaximum[kForceKinds] = {0.0, 0.0, 0.0};
    double faceNormalMaximum = 0.0;
    double faceMeanCurvatureMaximum = 0.0;
    double faceAreaMaximum = 0.0;
    double faceLegacyVolumeMaximum = 0.0;
    double faceEnergyMaximum = 0.0;
    if (checkpointLoadPassed)
    {
        for (int vertex = 0; vertex < kVertexCount; ++vertex)
        {
            const Force &before = mesh.vertices[vertex].force;
            const Force &after = restartMesh.vertices[vertex].force;
            const Matrix *beforeKinds[] = {
                &before.forceCurvature, &before.forceArea, &before.forceVolume};
            const Matrix *afterKinds[] = {
                &after.forceCurvature, &after.forceArea, &after.forceVolume};
            for (int kind = 0; kind < kForceKinds; ++kind)
                for (int axis = 0; axis < kAxes; ++axis)
                    forceFamilyMaximum[kind] = std::max(
                        forceFamilyMaximum[kind],
                        std::abs(beforeKinds[kind]->get(axis, 0) -
                                 afterKinds[kind]->get(axis, 0)));
        }
        for (int face = 0; face < kFaceCount; ++face)
        {
            const Face &before = mesh.faces[face];
            Face &after = restartMesh.faces[face];
            after.normVector = mat_calloc(kAxes, 1);
            for (int axis = 0; axis < kAxes; ++axis)
                faceNormalMaximum = std::max(
                    faceNormalMaximum,
                    std::abs(before.normVector.get(axis, 0) -
                             after.normVector.get(axis, 0)));
            faceMeanCurvatureMaximum = std::max(
                faceMeanCurvatureMaximum,
                std::abs(before.meanCurvature - after.meanCurvature));
            faceAreaMaximum = std::max(
                faceAreaMaximum,
                std::abs(before.elementArea - after.elementArea));
            faceLegacyVolumeMaximum = std::max(
                faceLegacyVolumeMaximum,
                std::abs(before.elementVolume - after.elementVolume));
            faceEnergyMaximum = std::max(
                faceEnergyMaximum, energy_delta(before.energy, after.energy));
        }
    }

    const bool passed = energyWriterPassed && faceFileExists &&
        checkpointWriterPassed && checkpointLoadPassed &&
        forceRoundtripMaximum == 0.0 && recordEnergyMaximum == 0.0;
    std::cout << std::setprecision(17) << '{'
              << "\"status\":\"" << (passed ? "passed" : "failed") << "\","
              << "\"proof_only\":true,"
              << "\"production_route_enabled\":false,"
              << "\"energy_force_writer_executed\":"
              << (energyWriterPassed ? "true" : "false") << ','
              << "\"element_face_energy_writer_executed\":"
              << (faceFileExists ? "true" : "false") << ','
              << "\"checkpoint_writer_executed\":"
              << (checkpointWriterPassed ? "true" : "false") << ','
              << "\"checkpoint_loader_executed\":"
              << (checkpointLoadPassed ? "true" : "false") << ','
              << "\"checkpoint_total_force_roundtrip_max_abs_difference\":"
              << forceRoundtripMaximum << ','
              << "\"checkpoint_record_energy_roundtrip_max_abs_difference\":"
              << recordEnergyMaximum << ','
              << "\"checkpoint_curvature_force_preserved\":"
              << (forceFamilyMaximum[0] == 0.0 ? "true" : "false") << ','
              << "\"checkpoint_curvature_force_max_abs_difference\":"
              << forceFamilyMaximum[0] << ','
              << "\"checkpoint_area_force_preserved\":"
              << (forceFamilyMaximum[1] == 0.0 ? "true" : "false") << ','
              << "\"checkpoint_area_force_max_abs_difference\":"
              << forceFamilyMaximum[1] << ','
              << "\"checkpoint_volume_force_preserved\":"
              << (forceFamilyMaximum[2] == 0.0 ? "true" : "false") << ','
              << "\"checkpoint_volume_force_max_abs_difference\":"
              << forceFamilyMaximum[2] << ','
              << "\"checkpoint_face_normals_preserved\":"
              << (faceNormalMaximum == 0.0 ? "true" : "false") << ','
              << "\"checkpoint_face_normals_max_abs_difference\":"
              << faceNormalMaximum << ','
              << "\"checkpoint_face_mean_curvature_preserved\":"
              << (faceMeanCurvatureMaximum == 0.0 ? "true" : "false") << ','
              << "\"checkpoint_face_mean_curvature_max_abs_difference\":"
              << faceMeanCurvatureMaximum << ','
              << "\"checkpoint_face_area_preserved\":"
              << (faceAreaMaximum == 0.0 ? "true" : "false") << ','
              << "\"checkpoint_face_area_max_abs_difference\":"
              << faceAreaMaximum << ','
              << "\"checkpoint_face_legacy_volume_preserved\":"
              << (faceLegacyVolumeMaximum == 0.0 ? "true" : "false") << ','
              << "\"checkpoint_face_legacy_volume_max_abs_difference\":"
              << faceLegacyVolumeMaximum << ','
              << "\"checkpoint_face_energy_preserved\":"
              << (faceEnergyMaximum == 0.0 ? "true" : "false") << ','
              << "\"checkpoint_face_energy_max_abs_difference\":"
              << faceEnergyMaximum
              << "}\n";
    return passed ? 0 : 4;
}
