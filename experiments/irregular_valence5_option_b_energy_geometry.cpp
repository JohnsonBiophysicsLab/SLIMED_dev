#include "linalg/Linear_algebra.hpp"
#include "mesh/Mesh.hpp"
#include "Parameters.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <string>
#include <vector>

namespace
{
constexpr int kFaceCount = 20;
constexpr int kSampleCount = 3;
constexpr int kRowCount = 7;
constexpr int kSourceCount = 12;
constexpr int kAxisCount = 3;
constexpr double kLegacyVolumeFactor = 0.16666666666;
constexpr std::array<std::array<double, 3>, kSampleCount> kSamplePlan{{
    {{1.0 / 6.0, 1.0 / 6.0, 1.0 / 3.0}},
    {{1.0 / 6.0, 4.0 / 6.0, 1.0 / 3.0}},
    {{4.0 / 6.0, 1.0 / 6.0, 1.0 / 3.0}},
}};

struct Package
{
    std::array<double, 8> parameters{};
    std::array<double, kFaceCount> regularization{};
    std::array<std::array<double, kAxisCount>, kSourceCount> coordinates{};
    std::array<std::array<int, 3>, kFaceCount> orientedFaces{};
    std::array<std::array<std::array<double, 3>, kSampleCount>, kFaceCount>
        samples{};
    std::array<std::array<std::array<std::array<double, kSourceCount>,
                                                    kRowCount>,
                                      kSampleCount>,
                          kFaceCount>
        rows{};
};

bool read_package(const std::string &path, Package &package)
{
    std::ifstream input(path);
    int faceCount = 0, sampleCount = 0, rowCount = 0, sourceCount = 0;
    if (!(input >> faceCount >> sampleCount >> rowCount >> sourceCount) ||
        faceCount != kFaceCount || sampleCount != kSampleCount ||
        rowCount != kRowCount || sourceCount != kSourceCount)
    {
        return false;
    }
    std::string tag;
    if (!(input >> tag) || tag != "PARAMETERS")
        return false;
    for (double &value : package.parameters)
        if (!(input >> value) || !std::isfinite(value))
            return false;
    if (!(input >> tag) || tag != "REGULARIZATION")
        return false;
    for (double &value : package.regularization)
        if (!(input >> value) || !std::isfinite(value))
            return false;
    int coordinateCount = 0;
    if (!(input >> tag >> coordinateCount) || tag != "COORDINATES" ||
        coordinateCount != kSourceCount)
        return false;
    for (int source = 0; source < kSourceCount; ++source)
    {
        int encodedSource = -1;
        if (!(input >> encodedSource) || encodedSource != source)
            return false;
        for (double &value : package.coordinates[source])
            if (!(input >> value) || !std::isfinite(value))
                return false;
    }
    for (int face = 0; face < kFaceCount; ++face)
    {
        int encodedFace = -1, ptexFace = -1;
        if (!(input >> tag >> encodedFace >> ptexFace) || tag != "FACE" ||
            encodedFace != face || ptexFace != face)
            return false;
        for (int &source : package.orientedFaces[face])
            if (!(input >> source) || source < 0 || source >= kSourceCount)
                return false;
        for (int sample = 0; sample < kSampleCount; ++sample)
        {
            int encodedSample = -1;
            if (!(input >> tag >> encodedSample) || tag != "SAMPLE" ||
                encodedSample != sample)
                return false;
            for (double &value : package.samples[face][sample])
                if (!(input >> value) || !std::isfinite(value))
                    return false;
            if (package.samples[face][sample] != kSamplePlan[sample])
                return false;
            for (int row = 0; row < kRowCount; ++row)
            {
                int encodedRow = -1;
                if (!(input >> tag >> encodedRow) || tag != "ROW" ||
                    encodedRow != row)
                    return false;
                for (double &coefficient : package.rows[face][sample][row])
                    if (!(input >> coefficient) || !std::isfinite(coefficient))
                        return false;
            }
        }
    }
    input >> std::ws;
    return input.peek() == std::char_traits<char>::eof();
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

bool all_finite(const std::vector<double> &values)
{
    return std::all_of(values.begin(), values.end(),
                       [](double value) { return std::isfinite(value); });
}

std::array<double, 3> evaluate_row(
    const std::array<double, kSourceCount> &row,
    const std::array<std::array<double, 3>, kSourceCount> &coordinates)
{
    std::array<double, 3> value{};
    for (int source = 0; source < kSourceCount; ++source)
        for (int axis = 0; axis < 3; ++axis)
            value[axis] += row[source] * coordinates[source][axis];
    return value;
}

std::array<double, 3> cross(const std::array<double, 3> &a,
                            const std::array<double, 3> &b)
{
    return {a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]};
}

double norm(const std::array<double, 3> &value)
{
    return std::sqrt(value[0] * value[0] + value[1] * value[1] +
                     value[2] * value[2]);
}
} // namespace

int main(int argc, char **argv)
{
    if (argc != 2)
    {
        std::cerr << "usage: irregular_valence5_option_b_energy_geometry PACKAGE\n";
        return 2;
    }
    Package package;
    if (!read_package(argv[1], package))
    {
        std::cerr << "invalid Option B energy/geometry package\n";
        return 3;
    }

    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Fixed;
    param.kCurv = package.parameters[0];
    const double spontaneousCurvature = package.parameters[1];
    param.uSurf = package.parameters[2];
    param.area0 = package.parameters[3];
    param.uVol = package.parameters[4];
    param.vol0 = package.parameters[5];
    param.area = package.parameters[6];
    param.vol = package.parameters[7];
    param.gaussQuadratureCoeff = Matrix(kSampleCount, 1, true);
    for (int sample = 0; sample < kSampleCount; ++sample)
        param.gaussQuadratureCoeff.set(sample, 0,
                                       package.samples[0][sample][2]);

    Mesh evaluator(param);
    std::vector<Matrix> coordinates(kSourceCount, Matrix(3, 1, true));
    for (int source = 0; source < kSourceCount; ++source)
        for (int axis = 0; axis < 3; ++axis)
            coordinates[source].set(axis, 0, package.coordinates[source][axis]);

    std::vector<double> curvature, regularization, normals, meanCurvature,
        area, legacyVolume;
    bool finite = true;
    for (int faceIndex = 0; faceIndex < kFaceCount; ++faceIndex)
    {
        std::vector<Matrix> shapeFunctions;
        for (int sample = 0; sample < kSampleCount; ++sample)
        {
            Matrix rows(kRowCount, kSourceCount, true);
            for (int row = 0; row < kRowCount; ++row)
                for (int source = 0; source < kSourceCount; ++source)
                    rows.set(row, source,
                             package.rows[faceIndex][sample][row][source]);
            shapeFunctions.push_back(std::move(rows));
        }
        Face face;
        face.index = faceIndex;
        double faceMean = 0.0, faceCurvature = 0.0;
        Matrix normal = mat_calloc(3, 1);
        Matrix fBend = mat_calloc(kSourceCount, 3);
        Matrix fArea = mat_calloc(kSourceCount, 3);
        Matrix fVolume = mat_calloc(kSourceCount, 3);
        evaluator.element_energy_force_regular(
            coordinates, face, spontaneousCurvature, faceMean, normal,
            faceCurvature, fBend, fArea, fVolume, false, &shapeFunctions);

        double faceArea = 0.0, faceVolume = 0.0;
        for (int sample = 0; sample < kSampleCount; ++sample)
        {
            const auto position = evaluate_row(
                package.rows[faceIndex][sample][0], package.coordinates);
            const auto dv = evaluate_row(
                package.rows[faceIndex][sample][1], package.coordinates);
            const auto dw = evaluate_row(
                package.rows[faceIndex][sample][2], package.coordinates);
            const auto tangentCross = cross(dv, dw);
            const double weight = package.samples[faceIndex][sample][2];
            faceArea += 0.5 * weight * norm(tangentCross);
            faceVolume += kLegacyVolumeFactor * weight * position[0] *
                          tangentCross[0];
        }
        curvature.push_back(faceCurvature);
        regularization.push_back(package.regularization[faceIndex]);
        meanCurvature.push_back(faceMean);
        area.push_back(faceArea);
        legacyVolume.push_back(faceVolume);
        for (int axis = 0; axis < 3; ++axis)
            normals.push_back(normal.get(axis, 0));
        finite = finite && std::isfinite(faceCurvature) &&
                 std::isfinite(faceMean) && std::isfinite(faceArea) &&
                 std::isfinite(faceVolume);
    }
    finite = finite && all_finite(curvature) && all_finite(regularization) &&
             all_finite(normals) && all_finite(meanCurvature) &&
             all_finite(area) && all_finite(legacyVolume);

    const double totalArea =
        std::accumulate(area.begin(), area.end(), 0.0);
    const double totalVolume =
        std::accumulate(legacyVolume.begin(), legacyVolume.end(), 0.0);
    const double curvatureEnergy =
        std::accumulate(curvature.begin(), curvature.end(), 0.0);
    const double regularizationEnergy =
        std::accumulate(regularization.begin(), regularization.end(), 0.0);
    const double areaEnergy = package.parameters[3] == 0.0
        ? 0.0
        : 0.5 * package.parameters[2] / package.parameters[3] *
              std::pow(totalArea - package.parameters[3], 2);
    const double volumeEnergy = package.parameters[5] == 0.0
        ? 0.0
        : 0.5 * package.parameters[4] / package.parameters[5] *
              std::pow(totalVolume - package.parameters[5], 2);
    std::vector<double> globalEnergy{
        curvatureEnergy, areaEnergy, volumeEnergy, 0.0, 0.0,
        regularizationEnergy, 0.0, 0.0, 0.0, 0.0,
    };
    globalEnergy[9] = std::accumulate(
        globalEnergy.begin(), globalEnergy.begin() + 9, 0.0);
    finite = finite && all_finite(globalEnergy);

    std::cout << std::setprecision(17) << '{';
    std::cout << "\"status\":\"" << (finite ? "passed" : "failed") << "\",";
    std::cout << "\"proof_only\":true,\"not_production_routing\":true,";
    std::cout << "\"existing_slimed_regular_evaluator_executed\":true,";
    std::cout << "\"global_energy\":"; print_values(globalEnergy);
    std::cout << ',';
    std::cout << "\"face_curvature_energy\":"; print_values(curvature);
    std::cout << ",\"face_regularization_energy\":"; print_values(regularization);
    std::cout << ",\"face_normals\":"; print_values(normals);
    std::cout << ",\"face_mean_curvature\":"; print_values(meanCurvature);
    std::cout << ",\"face_area\":"; print_values(area);
    std::cout << ",\"face_legacy_volume\":"; print_values(legacyVolume);
    std::cout << "}\n";
    return finite ? 0 : 4;
}
