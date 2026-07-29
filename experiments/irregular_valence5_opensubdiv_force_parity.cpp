#include "linalg/Linear_algebra.hpp"
#include "mesh/Mesh.hpp"
#include "Parameters.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace
{
constexpr int kFaceCount = 20;
constexpr int kSampleCount = 3;
constexpr int kRowCount = 7;
constexpr int kSourceCount = 12;
constexpr int kForceKindCount = 3;
constexpr int kAxisCount = 3;

struct Package
{
    std::array<double, 8> parameters{};
    std::array<std::array<double, kAxisCount>, kSourceCount> coordinates{};
    std::array<std::array<int, 3>, kFaceCount> orientedFaces{};
    std::array<
        std::array<
            std::array<std::array<double, kSourceCount>, kRowCount>,
            kSampleCount>,
        kFaceCount>
        rows{};
};

bool read_package(const std::string &path, Package &package)
{
    std::ifstream input(path);
    int faceCount = 0;
    int sampleCount = 0;
    int rowCount = 0;
    int sourceCount = 0;
    if (!(input >> faceCount >> sampleCount >> rowCount >> sourceCount) ||
        faceCount != kFaceCount || sampleCount != kSampleCount ||
        rowCount != kRowCount || sourceCount != kSourceCount)
    {
        return false;
    }

    std::string tag;
    if (!(input >> tag) || tag != "PARAMETERS")
    {
        return false;
    }
    for (double &value : package.parameters)
    {
        if (!(input >> value) || !std::isfinite(value))
        {
            return false;
        }
    }

    int coordinateCount = 0;
    if (!(input >> tag >> coordinateCount) || tag != "COORDINATES" ||
        coordinateCount != kSourceCount)
    {
        return false;
    }
    for (int source = 0; source < kSourceCount; ++source)
    {
        int encodedSource = -1;
        if (!(input >> encodedSource) || encodedSource != source)
        {
            return false;
        }
        for (double &value : package.coordinates[source])
        {
            if (!(input >> value) || !std::isfinite(value))
            {
                return false;
            }
        }
    }

    for (int face = 0; face < kFaceCount; ++face)
    {
        int encodedFace = -1;
        if (!(input >> encodedFace) || encodedFace != face)
        {
            return false;
        }
        for (int &source : package.orientedFaces[face])
        {
            if (!(input >> source) || source < 0 || source >= kSourceCount)
            {
                return false;
            }
        }
        for (int sample = 0; sample < kSampleCount; ++sample)
        {
            int encodedSample = -1;
            if (!(input >> encodedSample) || encodedSample != sample)
            {
                return false;
            }
            for (int row = 0; row < kRowCount; ++row)
            {
                for (double &coefficient : package.rows[face][sample][row])
                {
                    if (!(input >> coefficient) ||
                        !std::isfinite(coefficient))
                    {
                        return false;
                    }
                }
            }
        }
    }
    double trailing = 0.0;
    return !(input >> trailing);
}

void print_values(const std::vector<double> &values)
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
} // namespace

int main(int argc, char **argv)
{
    if (argc != 2)
    {
        std::cerr << "usage: irregular_valence5_opensubdiv_force_parity "
                     "PACKAGE\n";
        return 2;
    }

    Package package;
    if (!read_package(argv[1], package))
    {
        std::cerr << "invalid valence-5 OpenSubdiv force package\n";
        return 3;
    }

    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Fixed;
    param.kCurv = package.parameters[0];
    const double spontCurvature = package.parameters[1];
    param.uSurf = package.parameters[2];
    param.area0 = package.parameters[3];
    param.uVol = package.parameters[4];
    param.vol0 = package.parameters[5];
    param.area = package.parameters[6];
    param.vol = package.parameters[7];
    param.gaussQuadratureCoeff = Matrix(kSampleCount, 1, true);
    for (int sample = 0; sample < kSampleCount; ++sample)
    {
        param.gaussQuadratureCoeff.set(sample, 0, 1.0 / 3.0);
    }

    Mesh formulaMesh(param);
    std::vector<Matrix> coordinates(
        kSourceCount, Matrix(kAxisCount, 1, true));
    for (int source = 0; source < kSourceCount; ++source)
    {
        for (int axis = 0; axis < kAxisCount; ++axis)
        {
            coordinates[source].set(
                axis, 0, package.coordinates[source][axis]);
        }
    }

    std::vector<double> perFaceForces;
    std::vector<double> aggregateForces(
        kSourceCount * kForceKindCount * kAxisCount, 0.0);
    std::vector<double> faceBendingEnergy;
    std::vector<double> faceMeanCurvature;
    bool finite = true;
    bool nonzero = false;

    for (int faceIndex = 0; faceIndex < kFaceCount; ++faceIndex)
    {
        std::vector<Matrix> shapeFunctions;
        shapeFunctions.reserve(kSampleCount);
        for (int sample = 0; sample < kSampleCount; ++sample)
        {
            Matrix rows(kRowCount, kSourceCount, true);
            for (int row = 0; row < kRowCount; ++row)
            {
                for (int source = 0; source < kSourceCount; ++source)
                {
                    rows.set(
                        row, source, package.rows[faceIndex][sample][row][source]);
                }
            }
            shapeFunctions.push_back(std::move(rows));
        }

        Face face;
        face.index = faceIndex;
        face.spontCurvature = spontCurvature;
        double meanCurvature = 0.0;
        double bendingEnergy = 0.0;
        Matrix normal = mat_calloc(kAxisCount, 1);
        Matrix fBend = mat_calloc(kSourceCount, kAxisCount);
        Matrix fArea = mat_calloc(kSourceCount, kAxisCount);
        Matrix fVolume = mat_calloc(kSourceCount, kAxisCount);
        formulaMesh.element_energy_force_regular(
            coordinates,
            face,
            spontCurvature,
            meanCurvature,
            normal,
            bendingEnergy,
            fBend,
            fArea,
            fVolume,
            false,
            &shapeFunctions);

        faceBendingEnergy.push_back(bendingEnergy);
        faceMeanCurvature.push_back(meanCurvature);
        finite = finite && std::isfinite(bendingEnergy) &&
                 std::isfinite(meanCurvature);
        const std::array<const Matrix *, kForceKindCount> forceKinds{{
            &fBend,
            &fArea,
            &fVolume,
        }};
        for (int source = 0; source < kSourceCount; ++source)
        {
            for (int kind = 0; kind < kForceKindCount; ++kind)
            {
                for (int axis = 0; axis < kAxisCount; ++axis)
                {
                    const double value =
                        forceKinds[kind]->get(source, axis);
                    const int component =
                        9 * source + 3 * kind + axis;
                    finite = finite && std::isfinite(value);
                    nonzero = nonzero || std::abs(value) > 1.0e-12;
                    perFaceForces.push_back(value);
                    aggregateForces[component] += value;
                }
            }
        }
    }

    finite = finite && all_finite(perFaceForces) &&
             all_finite(aggregateForces) &&
             all_finite(faceBendingEnergy) &&
             all_finite(faceMeanCurvature);

    std::cout << std::setprecision(17);
    std::cout << '{';
    std::cout << "\"status\":\""
              << (finite && nonzero ? "passed" : "failed") << "\",";
    std::cout << "\"proof_only\":true,";
    std::cout << "\"not_production_routing\":true,";
    std::cout << "\"production_route_enabled\":false,";
    std::cout << "\"production_scatter_executed\":false,";
    std::cout << "\"opensubdiv_rows_evaluated_by_existing_force_algebra\":true,";
    std::cout << "\"face_count\":" << kFaceCount << ',';
    std::cout << "\"sample_count_per_face\":" << kSampleCount << ',';
    std::cout << "\"row_count\":" << kRowCount << ',';
    std::cout << "\"source_count\":" << kSourceCount << ',';
    std::cout << "\"finite\":" << (finite ? "true" : "false") << ',';
    std::cout << "\"nonzero_force\":" << (nonzero ? "true" : "false") << ',';
    std::cout << "\"per_face_source_forces\":";
    print_values(perFaceForces);
    std::cout << ",\"aggregate_source_forces\":";
    print_values(aggregateForces);
    std::cout << ",\"face_bending_energy\":";
    print_values(faceBendingEnergy);
    std::cout << ",\"face_mean_curvature\":";
    print_values(faceMeanCurvature);
    std::cout << "}\n";
    return finite && nonzero ? 0 : 4;
}
