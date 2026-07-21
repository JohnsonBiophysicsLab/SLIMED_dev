// Experimental, review-gated OpenSubdiv regular adapter proof.
//
// This file is compiled only by scripts/run_opensubdiv_regular_cpp_adapter_proof.sh
// when OPENSUBDIV_ROOT is supplied. It is not part of default SLIMED builds.

#include <opensubdiv/far/stencilTable.h>
#include <opensubdiv/far/stencilTableFactory.h>
#include <opensubdiv/far/topologyDescriptor.h>
#include <opensubdiv/far/topologyRefinerFactory.h>

#include "mesh/Mesh.hpp"
#include "mesh/OpenSubdiv_regular_evaluator.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <set>
#include <string>
#include <vector>

using namespace OpenSubdiv;

namespace
{
constexpr double kTolerance = 5.0e-6;
constexpr int kProductionRegularControlPointCount = 12;
constexpr int kProductionDerivativeRowCount = 7;
constexpr int kProductionSpatialDimension = 3;
constexpr int kProductionForceComponentsPerVertex = 9;

enum class WeightedRow
{
    Position = 0,
    FirstDerivativeV = 1,
    FirstDerivativeW = 2,
    SecondDerivativeVV = 3,
    SecondDerivativeWW = 4,
    MixedDerivativeVW = 5,
    MixedDerivativeWV = 6
};

struct Point
{
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;
};

struct MeshCase
{
    int numVertices = 0;
    int sampleFace = 0;
    std::vector<int> vertsPerFace;
    std::vector<int> vertIndices;
    std::vector<Point> points;
};

struct RegularSample
{
    double v = 0.0;
    double w = 0.0;
    double u = 0.0;
    double weight = 0.0;
};

struct WeightedSampleProof
{
    std::vector<int> sourceIds;
    std::array<std::vector<double>, 7> rowWeights;
    std::array<std::array<double, 3>, 7> evaluatedRows{};

    double row_weight(WeightedRow row, int sourceId) const
    {
        double value = 0.0;
        const int rowIndex = static_cast<int>(row);
        for (int col = 0; col < static_cast<int>(sourceIds.size()); ++col)
        {
            if (sourceIds[col] == sourceId)
            {
                value += rowWeights[rowIndex][col];
            }
        }
        return value;
    }
};

struct Vec3d
{
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
};

struct Mat3d
{
    double v[3][3] = {{0.0, 0.0, 0.0},
                      {0.0, 0.0, 0.0},
                      {0.0, 0.0, 0.0}};
};

struct ActualForceParams
{
    double kCurv = 47.5;
    double spontCurv = 0.18;
    double uSurf = 130.0;
    double area0 = 2.75;
    double area = 0.0;
    double uVol = 65.0;
    double vol0 = 0.82;
    double vol = 0.0;
};

struct ActualForceResult
{
    double meanCurv = 0.0;
    double eBend = 0.0;
    Vec3d normVector;
    std::vector<double> fBend;
    std::vector<double> fArea;
    std::vector<double> fVolume;
};

struct ProductionDryRunResult
{
    double meanCurv = 0.0;
    double eBend = 0.0;
    Vec3d normVector;
    std::vector<double> fBend;
    std::vector<double> fArea;
    std::vector<double> fVolume;
    double maxForceRowDifference = 0.0;
    double maxScalarDifference = 0.0;
    bool finite = false;
    bool matchesProofLocalRows = false;
};

struct VisibleObservableResult
{
    double area = 0.0;
    double fullDotVolume = 0.0;
    double legacyVisibleVolume = 0.0;
    double productionArea = 0.0;
    double productionLegacyVisibleVolume = 0.0;
    double maxAreaVolumeDifference = 0.0;
    bool finite = false;
    bool matchesProductionAreaVolume = false;
};

struct AccumulationParityResult
{
    int simulatedFaceContributions = 0;
    int simulatedOpenMpThreadBuffers = 0;
    double maxDifference = 0.0;
    double maxAbsSerialComponent = 0.0;
    bool finite = false;
    bool nonzero = false;
    bool matchesSerialOpenMpShape = false;
};

struct DoubleLimitStencilFeasibilityResult
{
    bool stencilTableCreated = false;
    bool stencilSourcesMatchFaceOneRing = true;
    bool mixedRowsDuplicated = true;
    int sampleCount = 0;
    double maxFloatStencilVsSlimedRowDifference = 0.0;
    double maxDoubleStencilVsSlimedRowDifference = 0.0;
    double maxDoubleStencilVsFloatStencilDifference = 0.0;
    bool doubleRowsMatchSlimedAtStrictPrecision = false;
};

class ScopedEnvVar
{
public:
    ScopedEnvVar(const char *name, const char *value)
        : name_(name)
    {
        const char *previous = std::getenv(name_);
        if (previous != nullptr)
        {
            hadPrevious_ = true;
            previous_ = previous;
        }
        if (value == nullptr)
        {
            unsetenv(name_);
        }
        else
        {
            setenv(name_, value, 1);
        }
    }

    ~ScopedEnvVar()
    {
        if (hadPrevious_)
        {
            setenv(name_, previous_.c_str(), 1);
        }
        else
        {
            unsetenv(name_);
        }
    }

private:
    const char *name_;
    bool hadPrevious_ = false;
    std::string previous_;
};

class ScopedCoutSilencer
{
public:
    ScopedCoutSilencer()
        : previousCout_(std::cout.rdbuf(coutSink_.rdbuf())),
          previousCerr_(std::cerr.rdbuf(cerrSink_.rdbuf()))
    {
    }

    ~ScopedCoutSilencer()
    {
        std::cout.rdbuf(previousCout_);
        std::cerr.rdbuf(previousCerr_);
    }

private:
    std::ostringstream coutSink_;
    std::ostringstream cerrSink_;
    std::streambuf *previousCout_ = nullptr;
    std::streambuf *previousCerr_ = nullptr;
};

void append_face(MeshCase &mesh, int a, int b, int c)
{
    mesh.vertsPerFace.push_back(3);
    mesh.vertIndices.push_back(a);
    mesh.vertIndices.push_back(b);
    mesh.vertIndices.push_back(c);
}

MeshCase make_regular_lattice_case()
{
    MeshCase mesh;
    const int n = 6;
    mesh.numVertices = (n + 1) * (n + 1);
    mesh.points.reserve(mesh.numVertices);
    for (int j = 0; j <= n; ++j)
    {
        for (int i = 0; i <= n; ++i)
        {
            mesh.points.push_back(Point{
                static_cast<float>(i + 0.5 * j),
                static_cast<float>(0.8660254037844386 * j),
                static_cast<float>(0.03 * std::sin(0.7 * (i + j)))});
        }
    }

    const auto id = [n](int i, int j) { return j * (n + 1) + i; };
    for (int j = 0; j < n; ++j)
    {
        for (int i = 0; i < n; ++i)
        {
            if (i == 2 && j == 2)
            {
                mesh.sampleFace = static_cast<int>(mesh.vertsPerFace.size());
            }
            append_face(mesh, id(i, j), id(i + 1, j), id(i, j + 1));
            append_face(mesh, id(i + 1, j), id(i + 1, j + 1), id(i, j + 1));
        }
    }
    return mesh;
}

std::vector<int> regular_lattice_face_one_ring_source_ids()
{
    return {9, 15, 10, 16, 22, 11, 17, 23, 29, 18, 24, 30};
}

Vec3d make_vec(double x, double y, double z)
{
    Vec3d out;
    out.x = x;
    out.y = y;
    out.z = z;
    return out;
}

Vec3d make_vec(const std::array<double, 3> &values)
{
    return make_vec(values[0], values[1], values[2]);
}

double get_axis(const Vec3d &value, int axis)
{
    if (axis == 0)
    {
        return value.x;
    }
    return axis == 1 ? value.y : value.z;
}

void set_axis(Vec3d &value, int axis, double component)
{
    if (axis == 0)
    {
        value.x = component;
    }
    else if (axis == 1)
    {
        value.y = component;
    }
    else
    {
        value.z = component;
    }
}

Vec3d operator+(const Vec3d &lhs, const Vec3d &rhs)
{
    return make_vec(lhs.x + rhs.x, lhs.y + rhs.y, lhs.z + rhs.z);
}

Vec3d operator-(const Vec3d &lhs, const Vec3d &rhs)
{
    return make_vec(lhs.x - rhs.x, lhs.y - rhs.y, lhs.z - rhs.z);
}

Vec3d operator*(const Vec3d &value, double scale)
{
    return make_vec(value.x * scale, value.y * scale, value.z * scale);
}

Vec3d operator*(double scale, const Vec3d &value)
{
    return value * scale;
}

Vec3d &operator+=(Vec3d &lhs, const Vec3d &rhs)
{
    lhs.x += rhs.x;
    lhs.y += rhs.y;
    lhs.z += rhs.z;
    return lhs;
}

double dot(const Vec3d &lhs, const Vec3d &rhs)
{
    return lhs.x * rhs.x + lhs.y * rhs.y + lhs.z * rhs.z;
}

Vec3d cross(const Vec3d &lhs, const Vec3d &rhs)
{
    return make_vec(lhs.y * rhs.z - lhs.z * rhs.y,
                    lhs.z * rhs.x - lhs.x * rhs.z,
                    lhs.x * rhs.y - lhs.y * rhs.x);
}

double norm(const Vec3d &value)
{
    return std::sqrt(dot(value, value));
}

Vec3d normalized(const Vec3d &value)
{
    const double length = norm(value);
    if (length == 0.0)
    {
        return Vec3d();
    }
    return value * (1.0 / length);
}

bool finite_vec(const Vec3d &value)
{
    return std::isfinite(value.x) && std::isfinite(value.y) &&
           std::isfinite(value.z);
}

Mat3d kron(const Vec3d &lhs, const Vec3d &rhs)
{
    Mat3d out;
    for (int row = 0; row < 3; ++row)
    {
        for (int col = 0; col < 3; ++col)
        {
            out.v[row][col] = get_axis(lhs, row) * get_axis(rhs, col);
        }
    }
    return out;
}

Mat3d &operator+=(Mat3d &lhs, const Mat3d &rhs)
{
    for (int row = 0; row < 3; ++row)
    {
        for (int col = 0; col < 3; ++col)
        {
            lhs.v[row][col] += rhs.v[row][col];
        }
    }
    return lhs;
}

Mat3d operator*(const Mat3d &value, double scale)
{
    Mat3d out;
    for (int row = 0; row < 3; ++row)
    {
        for (int col = 0; col < 3; ++col)
        {
            out.v[row][col] = value.v[row][col] * scale;
        }
    }
    return out;
}

Vec3d row_vec_times_matrix(const Vec3d &row, const Mat3d &matrix)
{
    Vec3d out;
    for (int col = 0; col < 3; ++col)
    {
        double value = 0.0;
        for (int axis = 0; axis < 3; ++axis)
        {
            value += get_axis(row, axis) * matrix.v[axis][col];
        }
        set_axis(out, col, value);
    }
    return out;
}

void add_force(std::vector<double> &target,
               int vertex,
               const Vec3d &force,
               double scale)
{
    target[3 * vertex] += scale * force.x;
    target[3 * vertex + 1] += scale * force.y;
    target[3 * vertex + 2] += scale * force.z;
}

double max_abs_component(const std::vector<double> &values)
{
    double out = 0.0;
    for (double value : values)
    {
        out = std::max(out, std::abs(value));
    }
    return out;
}

double l1_component_sum(const std::vector<double> &values)
{
    double out = 0.0;
    for (double value : values)
    {
        out += std::abs(value);
    }
    return out;
}

double max_abs_component_delta(const std::vector<double> &lhs,
                               const std::vector<double> &rhs)
{
    double out = 0.0;
    for (int i = 0; i < static_cast<int>(lhs.size()); ++i)
    {
        out = std::max(out, std::abs(lhs[i] - rhs[i]));
    }
    return out;
}

double max_abs_scalar_delta(double lhs, double rhs)
{
    return std::abs(lhs - rhs);
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

Matrix make_shape_function_matrix(const WeightedSampleProof &proof)
{
    Matrix shapeFunction(kProductionDerivativeRowCount,
                         kProductionRegularControlPointCount,
                         true);
    for (int row = 0; row < kProductionDerivativeRowCount; ++row)
    {
        for (int col = 0; col < kProductionRegularControlPointCount; ++col)
        {
            shapeFunction.set(row, col, proof.rowWeights[row][col]);
        }
    }
    return shapeFunction;
}

std::vector<Matrix> make_production_coordinate_columns(
    const MeshCase &mesh,
    const std::vector<int> &sourceIds)
{
    std::vector<Matrix> coordinates(sourceIds.size());
    for (int row = 0; row < static_cast<int>(sourceIds.size()); ++row)
    {
        const Point &point = mesh.points[sourceIds[row]];
        coordinates[row] = Matrix(3, 1, true);
        coordinates[row].set(0, 0, point.x);
        coordinates[row].set(1, 0, point.y);
        coordinates[row].set(2, 0, point.z);
    }
    return coordinates;
}

void append_matrix_rows(const Matrix &matrix, std::vector<double> &target)
{
    for (int row = 0; row < matrix.nrow(); ++row)
    {
        for (int axis = 0; axis < matrix.ncol(); ++axis)
        {
            target.push_back(matrix.get(row, axis));
        }
    }
}

Vec3d make_vec_from_column(const Matrix &matrix)
{
    return make_vec(matrix.get(0, 0), matrix.get(1, 0), matrix.get(2, 0));
}

std::array<RegularSample, 3> frozen_regular_samples()
{
    return {{
        {1.0 / 6.0, 1.0 / 6.0, 4.0 / 6.0, 1.0 / 3.0},
        {1.0 / 6.0, 4.0 / 6.0, 1.0 / 6.0, 1.0 / 3.0},
        {4.0 / 6.0, 1.0 / 6.0, 1.0 / 6.0, 1.0 / 3.0},
    }};
}

Far::TopologyRefiner *create_refiner(const MeshCase &mesh)
{
    using Descriptor = Far::TopologyDescriptor;

    Descriptor desc;
    desc.numVertices = mesh.numVertices;
    desc.numFaces = static_cast<int>(mesh.vertsPerFace.size());
    desc.numVertsPerFace = mesh.vertsPerFace.data();
    desc.vertIndicesPerFace = mesh.vertIndices.data();

    Sdc::Options options;
    options.SetVtxBoundaryInterpolation(Sdc::Options::VTX_BOUNDARY_EDGE_ONLY);

    return Far::TopologyRefinerFactory<Descriptor>::Create(
        desc,
        Far::TopologyRefinerFactory<Descriptor>::Options(
            Sdc::SCHEME_LOOP, options));
}

double stencil_weight_for_source(const Far::LimitStencil &stencil,
                                 const float *weights,
                                 int sourceId)
{
    double result = 0.0;
    const Far::Index *indices = stencil.GetVertexIndices();
    for (int i = 0; i < stencil.GetSize(); ++i)
    {
        if (indices[i] == sourceId)
        {
            result += static_cast<double>(weights[i]);
        }
    }
    return result;
}

std::array<double, 3> evaluate_row_by_original_ids(
    const MeshCase &mesh,
    const std::vector<int> &sourceIds,
    const std::vector<double> &weights)
{
    std::array<double, 3> out = {0.0, 0.0, 0.0};
    for (int col = 0; col < static_cast<int>(sourceIds.size()); ++col)
    {
        const Point &point = mesh.points[sourceIds[col]];
        out[0] += weights[col] * point.x;
        out[1] += weights[col] * point.y;
        out[2] += weights[col] * point.z;
    }
    return out;
}

std::array<double, 3> evaluate_row_by_stencil_order(
    const MeshCase &mesh,
    const Far::LimitStencil &stencil,
    const float *weights)
{
    std::array<double, 3> out = {0.0, 0.0, 0.0};
    const Far::Index *indices = stencil.GetVertexIndices();
    for (int i = 0; i < stencil.GetSize(); ++i)
    {
        const Point &point = mesh.points[indices[i]];
        out[0] += static_cast<double>(weights[i]) * point.x;
        out[1] += static_cast<double>(weights[i]) * point.y;
        out[2] += static_cast<double>(weights[i]) * point.z;
    }
    return out;
}

double max_abs_delta(const std::array<double, 3> &lhs,
                     const std::array<double, 3> &rhs)
{
    return std::max(std::abs(lhs[0] - rhs[0]),
                    std::max(std::abs(lhs[1] - rhs[1]),
                             std::abs(lhs[2] - rhs[2])));
}

WeightedSampleProof adapt_regular_sample(const MeshCase &mesh,
                                         const Far::LimitStencil &stencil,
                                         const std::vector<int> &sourceIds)
{
    const std::array<const float *, 7> rowPtrs = {
        stencil.GetWeights(),
        stencil.GetDuWeights(),
        stencil.GetDvWeights(),
        stencil.GetDuuWeights(),
        stencil.GetDvvWeights(),
        stencil.GetDuvWeights(),
        stencil.GetDuvWeights(),
    };

    WeightedSampleProof proof;
    proof.sourceIds = sourceIds;
    for (int row = 0; row < 7; ++row)
    {
        proof.rowWeights[row].assign(sourceIds.size(), 0.0);
        for (int col = 0; col < static_cast<int>(sourceIds.size()); ++col)
        {
            proof.rowWeights[row][col] =
                stencil_weight_for_source(stencil, rowPtrs[row], sourceIds[col]);
        }
        proof.evaluatedRows[row] =
            evaluate_row_by_original_ids(mesh, sourceIds, proof.rowWeights[row]);
    }
    return proof;
}

double stencil_weight_for_source(
    const Far::LimitStencilReal<double> &stencil,
    const double *weights,
    int sourceId)
{
    double result = 0.0;
    const Far::Index *indices = stencil.GetVertexIndices();
    for (int i = 0; i < stencil.GetSize(); ++i)
    {
        if (indices[i] == sourceId)
        {
            result += weights[i];
        }
    }
    return result;
}

WeightedSampleProof adapt_regular_sample(
    const MeshCase &mesh,
    const Far::LimitStencilReal<double> &stencil,
    const std::vector<int> &sourceIds)
{
    const std::array<const double *, 7> rowPtrs = {
        stencil.GetWeights(),
        stencil.GetDuWeights(),
        stencil.GetDvWeights(),
        stencil.GetDuuWeights(),
        stencil.GetDvvWeights(),
        stencil.GetDuvWeights(),
        stencil.GetDuvWeights(),
    };

    WeightedSampleProof proof;
    proof.sourceIds = sourceIds;
    for (int row = 0; row < 7; ++row)
    {
        proof.rowWeights[row].assign(sourceIds.size(), 0.0);
        for (int col = 0; col < static_cast<int>(sourceIds.size()); ++col)
        {
            proof.rowWeights[row][col] =
                stencil_weight_for_source(stencil, rowPtrs[row], sourceIds[col]);
        }
        proof.evaluatedRows[row] =
            evaluate_row_by_original_ids(mesh, sourceIds, proof.rowWeights[row]);
    }
    return proof;
}

DoubleLimitStencilFeasibilityResult evaluate_double_limit_stencil_feasibility(
    const MeshCase &mesh,
    Far::TopologyRefiner &refiner,
    const std::vector<int> &faceOneRing,
    const std::array<RegularSample, 3> &samples,
    const std::vector<WeightedSampleProof> &floatStencilProofs)
{
    DoubleLimitStencilFeasibilityResult result;
    double s[3] = {samples[0].v, samples[1].v, samples[2].v};
    double t[3] = {samples[0].w, samples[1].w, samples[2].w};

    typedef Far::LimitStencilTableFactoryReal<double> DoubleFactory;
    DoubleFactory::LocationArray location;
    location.ptexIdx = mesh.sampleFace;
    location.numLocations = static_cast<int>(samples.size());
    location.s = s;
    location.t = t;
    DoubleFactory::LocationArrayVec locations;
    locations.push_back(location);

    DoubleFactory::Options options;
    options.generate1stDerivatives = true;
    options.generate2ndDerivatives = true;
    const Far::LimitStencilTableReal<double> *stencils =
        DoubleFactory::Create(refiner, locations, 0, 0, options);
    if (stencils == nullptr)
    {
        return result;
    }
    result.stencilTableCreated = true;

    Param directSourceParam;
    directSourceParam.VERBOSE_MODE = false;
    Mesh directMesh(directSourceParam);
    const Param &directParam = directMesh.param;
    if (directParam.shapeFunctions.size() != samples.size() ||
        stencils->GetNumStencils() != static_cast<int>(samples.size()))
    {
        delete stencils;
        return result;
    }

    const std::set<int> expectedSources(faceOneRing.begin(), faceOneRing.end());
    for (int sampleIndex = 0; sampleIndex < stencils->GetNumStencils(); ++sampleIndex)
    {
        const Far::LimitStencilReal<double> stencil =
            stencils->GetLimitStencil(sampleIndex);
        const Far::Index *indices = stencil.GetVertexIndices();
        std::set<int> stencilSources;
        for (int i = 0; i < stencil.GetSize(); ++i)
        {
            stencilSources.insert(indices[i]);
        }
        result.stencilSourcesMatchFaceOneRing =
            result.stencilSourcesMatchFaceOneRing &&
            stencilSources == expectedSources;

        WeightedSampleProof proof =
            adapt_regular_sample(mesh, stencil, faceOneRing);
        for (int row = 0; row < kProductionDerivativeRowCount; ++row)
        {
            for (int col = 0; col < static_cast<int>(faceOneRing.size()); ++col)
            {
                const double directValue =
                    directParam.shapeFunctions[sampleIndex].get(row, col);
                result.maxDoubleStencilVsSlimedRowDifference = std::max(
                    result.maxDoubleStencilVsSlimedRowDifference,
                    std::abs(proof.rowWeights[row][col] - directValue));
                result.maxFloatStencilVsSlimedRowDifference = std::max(
                    result.maxFloatStencilVsSlimedRowDifference,
                    std::abs(floatStencilProofs[sampleIndex].rowWeights[row][col] -
                             directValue));
                result.maxDoubleStencilVsFloatStencilDifference = std::max(
                    result.maxDoubleStencilVsFloatStencilDifference,
                    std::abs(proof.rowWeights[row][col] -
                             floatStencilProofs[sampleIndex].rowWeights[row][col]));
            }
        }
        result.mixedRowsDuplicated =
            result.mixedRowsDuplicated &&
            proof.rowWeights[static_cast<int>(WeightedRow::MixedDerivativeVW)] ==
                proof.rowWeights[static_cast<int>(WeightedRow::MixedDerivativeWV)];
        ++result.sampleCount;
    }
    delete stencils;

    result.doubleRowsMatchSlimedAtStrictPrecision =
        result.stencilTableCreated && result.stencilSourcesMatchFaceOneRing &&
        result.mixedRowsDuplicated &&
        result.sampleCount == static_cast<int>(samples.size()) &&
        result.maxDoubleStencilVsSlimedRowDifference <= 1.0e-12;
    return result;
}

void accumulate_area_volume(const WeightedSampleProof &proof,
                            double quadratureCoeff,
                            ActualForceParams &params)
{
    const Vec3d x = make_vec(proof.evaluatedRows[0]);
    const Vec3d a1 = make_vec(proof.evaluatedRows[1]);
    const Vec3d a2 = make_vec(proof.evaluatedRows[2]);
    const Vec3d xa = cross(a1, a2);
    const double sqa = norm(xa);
    params.area += 0.5 * quadratureCoeff * sqa;
    params.vol += (1.0 / 6.0) * quadratureCoeff * dot(x, xa);
}

void accumulate_visible_observable_sample(const WeightedSampleProof &proof,
                                          double quadratureCoeff,
                                          VisibleObservableResult &result)
{
    const Vec3d x = make_vec(proof.evaluatedRows[0]);
    const Vec3d a1 = make_vec(proof.evaluatedRows[1]);
    const Vec3d a2 = make_vec(proof.evaluatedRows[2]);
    const Vec3d xa = cross(a1, a2);
    const double sqa = norm(xa);
    result.area += 0.5 * quadratureCoeff * sqa;
    result.fullDotVolume += (1.0 / 6.0) * quadratureCoeff * dot(x, xa);
    result.legacyVisibleVolume += (1.0 / 6.0) * quadratureCoeff * x.x * xa.x;
}

bool accumulate_actual_force_sample(const WeightedSampleProof &proof,
                                    double quadratureCoeff,
                                    const ActualForceParams &params,
                                    ActualForceResult &result,
                                    std::set<int> &forceSourceIds)
{
    const Vec3d x = make_vec(proof.evaluatedRows[0]);
    const Vec3d a_1 = make_vec(proof.evaluatedRows[1]);
    const Vec3d a_2 = make_vec(proof.evaluatedRows[2]);
    const Vec3d a_11 = make_vec(proof.evaluatedRows[3]);
    const Vec3d a_22 = make_vec(proof.evaluatedRows[4]);
    const Vec3d a_12 = make_vec(proof.evaluatedRows[5]);
    const Vec3d a_21 = make_vec(proof.evaluatedRows[6]);

    const Vec3d xa = cross(a_1, a_2);
    const double sqa = norm(xa);
    if (sqa == 0.0)
    {
        return false;
    }
    const double tmpSqaSqrInv = 1.0 / sqa / sqa;

    const Vec3d xa_1 = cross(a_11, a_2) + cross(a_1, a_21);
    const Vec3d xa_2 = cross(a_12, a_2) + cross(a_1, a_22);
    const double sqa_1 = dot(xa, xa_1) / sqa;
    const double sqa_2 = dot(xa, xa_2) / sqa;
    const Vec3d a_3 = xa * (1.0 / sqa);
    const Vec3d a_31 = (xa_1 * sqa - xa * sqa_1) * tmpSqaSqrInv;
    const Vec3d a_32 = (xa_2 * sqa - xa * sqa_2) * tmpSqaSqrInv;

    const Vec3d tmpA2x3 = cross(a_2, a_3);
    const Vec3d tmpA3x1 = cross(a_3, a_1);
    const Vec3d a1 = tmpA2x3 * (1.0 / sqa);
    const Vec3d a2 = tmpA3x1 * (1.0 / sqa);
    const Vec3d a11 =
        ((cross(a_21, a_3) + cross(a_2, a_31)) * sqa -
         tmpA2x3 * sqa_1) *
        tmpSqaSqrInv;
    const Vec3d a12 =
        ((cross(a_22, a_3) + cross(a_2, a_32)) * sqa -
         tmpA2x3 * sqa_2) *
        tmpSqaSqrInv;
    const Vec3d a21 =
        ((cross(a_31, a_1) + cross(a_3, a_11)) * sqa -
         tmpA3x1 * sqa_1) *
        tmpSqaSqrInv;
    const Vec3d a22 =
        ((cross(a_32, a_1) + cross(a_3, a_12)) * sqa -
         tmpA3x1 * sqa_2) *
        tmpSqaSqrInv;

    const double hCurv = 0.5 * (dot(a1, a_31) + dot(a2, a_32));
    const double tmpConstF =
        -params.kCurv * (2.0 * hCurv - params.spontCurv);
    const double tmpConstL =
        params.kCurv * 0.5 * std::pow(2.0 * hCurv - params.spontCurv, 2.0);
    const Vec3d n1Be =
        (a_31 * dot(a1, a1) + a_32 * dot(a1, a2)) * tmpConstF +
        a1 * tmpConstL;
    const Vec3d n2Be =
        (a_31 * dot(a2, a1) + a_32 * dot(a2, a2)) * tmpConstF +
        a2 * tmpConstL;
    const Vec3d m1Be = a1 * (-tmpConstF);
    const Vec3d m2Be = a2 * (-tmpConstF);

    const double areaScale =
        (params.uSurf == 0.0 || params.area0 == 0.0)
            ? 0.0
            : (params.uSurf / params.area0) * (params.area - params.area0);
    const Vec3d n1Cons = a1 * areaScale;
    const Vec3d n2Cons = a2 * areaScale;

    const double tmpEvol =
        (params.uVol == 0.0 || params.vol0 == 0.0)
            ? 0.0
            : (params.uVol / params.vol0) * (params.vol - params.vol0) / 3.0;
    const Vec3d n1Conv =
        (a1 * dot(x, a_3) - a_3 * dot(x, a1)) * tmpEvol;
    const Vec3d n2Conv =
        (a2 * dot(x, a_3) - a_3 * dot(x, a2)) * tmpEvol;

    const double eBendTmp =
        0.5 * params.kCurv * sqa *
        std::pow(2.0 * hCurv - params.spontCurv, 2.0);
    const double halfCoeff = 0.5 * quadratureCoeff;

    for (int col = 0; col < static_cast<int>(proof.sourceIds.size()); ++col)
    {
        const int vertex = proof.sourceIds[col];
        forceSourceIds.insert(vertex);
        const double sf0 = proof.rowWeights[0][col];
        const double sf1 = proof.rowWeights[1][col];
        const double sf2 = proof.rowWeights[2][col];
        const double sf3 = proof.rowWeights[3][col];
        const double sf4 = proof.rowWeights[4][col];
        const double sf5 = proof.rowWeights[5][col];
        const double sf6 = proof.rowWeights[6][col];

        Mat3d da1;
        da1 += kron(a1, a_3) * -sf3;
        da1 += kron(a11, a_3) * -sf1;
        da1 += kron(a1, a_31) * -sf1;
        da1 += kron(a2, a_3) * -sf6;
        da1 += kron(a21, a_3) * -sf2;
        da1 += kron(a2, a_31) * -sf2;

        Mat3d da2;
        da2 += kron(a1, a_3) * -sf5;
        da2 += kron(a12, a_3) * -sf1;
        da2 += kron(a1, a_32) * -sf1;
        da2 += kron(a2, a_3) * -sf4;
        da2 += kron(a22, a_3) * -sf2;
        da2 += kron(a2, a_32) * -sf2;

        Vec3d tempfBe = row_vec_times_matrix(m1Be, da1) +
                        row_vec_times_matrix(m2Be, da2) +
                        n1Be * sf1 + n2Be * sf2;
        tempfBe = tempfBe * -sqa;

        const Vec3d tempfCons = (n1Cons * sf1 + n2Cons * sf2) * -sqa;
        const Vec3d tempfConv =
            (n1Conv * sf1 + n2Conv * sf2 + a_3 * (tmpEvol * sf0)) *
            -sqa;

        add_force(result.fBend, vertex, tempfBe, halfCoeff);
        add_force(result.fArea, vertex, tempfCons, halfCoeff);
        add_force(result.fVolume, vertex, tempfConv, halfCoeff);
    }

    result.meanCurv += halfCoeff * hCurv;
    result.eBend += halfCoeff * eBendTmp;
    result.normVector += a_3 * halfCoeff;
    return finite_vec(x) && finite_vec(a_1) && finite_vec(a_2) &&
           finite_vec(a_11) && finite_vec(a_22) && finite_vec(a_12) &&
           finite_vec(a_21);
}

std::set<int> stencil_source_set(const Far::LimitStencil &stencil)
{
    std::set<int> result;
    const Far::Index *indices = stencil.GetVertexIndices();
    for (int i = 0; i < stencil.GetSize(); ++i)
    {
        result.insert(indices[i]);
    }
    return result;
}

bool same_set(const std::set<int> &lhs, const std::vector<int> &rhs)
{
    return lhs == std::set<int>(rhs.begin(), rhs.end());
}

bool rows_equal(const std::vector<double> &lhs, const std::vector<double> &rhs)
{
    if (lhs.size() != rhs.size())
    {
        return false;
    }
    for (int i = 0; i < static_cast<int>(lhs.size()); ++i)
    {
        if (std::abs(lhs[i] - rhs[i]) > 0.0)
        {
            return false;
        }
    }
    return true;
}

void print_int_vector(const std::vector<int> &values)
{
    std::cout << "[";
    for (int i = 0; i < static_cast<int>(values.size()); ++i)
    {
        if (i > 0)
        {
            std::cout << ",";
        }
        std::cout << values[i];
    }
    std::cout << "]";
}

void print_int_set(const std::set<int> &values)
{
    std::cout << "[";
    bool first = true;
    for (int value : values)
    {
        if (!first)
        {
            std::cout << ",";
        }
        first = false;
        std::cout << value;
    }
    std::cout << "]";
}

void print_vec3(const Vec3d &values)
{
    std::cout << "[" << values.x << "," << values.y << "," << values.z << "]";
}

double max_production_scatter_delta(const std::vector<double> &productionBuffer,
                                    const std::vector<double> &fBend,
                                    const std::vector<double> &fArea,
                                    const std::vector<double> &fVolume)
{
    double out = 0.0;
    const int vertexCount = static_cast<int>(fBend.size() / kProductionSpatialDimension);
    for (int vertex = 0; vertex < vertexCount; ++vertex)
    {
        for (int axis = 0; axis < kProductionSpatialDimension; ++axis)
        {
            out = std::max(out,
                           std::abs(productionBuffer[kProductionForceComponentsPerVertex * vertex + axis] -
                                    fBend[kProductionSpatialDimension * vertex + axis]));
            out = std::max(out,
                           std::abs(productionBuffer[kProductionForceComponentsPerVertex * vertex + 3 + axis] -
                                    fArea[kProductionSpatialDimension * vertex + axis]));
            out = std::max(out,
                           std::abs(productionBuffer[kProductionForceComponentsPerVertex * vertex + 6 + axis] -
                                    fVolume[kProductionSpatialDimension * vertex + axis]));
        }
    }
    return out;
}

void add_rows_to_production_force_buffer(std::vector<double> &buffer,
                                         const std::vector<int> &faceOneRing,
                                         const std::vector<double> &fBendRows,
                                         const std::vector<double> &fAreaRows,
                                         const std::vector<double> &fVolumeRows,
                                         double scale)
{
    for (int row = 0; row < static_cast<int>(faceOneRing.size()); ++row)
    {
        const int sourceId = faceOneRing[row];
        const int baseIndex = sourceId * kProductionForceComponentsPerVertex;
        for (int axis = 0; axis < kProductionSpatialDimension; ++axis)
        {
            const int localIndex = row * kProductionSpatialDimension + axis;
            buffer[baseIndex + axis] += scale * fBendRows[localIndex];
            buffer[baseIndex + 3 + axis] += scale * fAreaRows[localIndex];
            buffer[baseIndex + 6 + axis] += scale * fVolumeRows[localIndex];
        }
    }
}

AccumulationParityResult run_serial_openmp_accumulation_parity_proof(
    int vertexCount,
    const std::vector<int> &faceOneRing,
    const std::vector<double> &fBendRows,
    const std::vector<double> &fAreaRows,
    const std::vector<double> &fVolumeRows)
{
    // Proof-only mirror of production's per-thread force buffers and final
    // deterministic thread-index reduction. It does not enter production routing.
    const std::array<double, 4> contributionScales = {{1.0, 1.0, -0.25, 0.5}};
    const int simulatedThreadBuffers = 3;
    std::vector<double> serial(vertexCount * kProductionForceComponentsPerVertex, 0.0);
    std::vector<std::vector<double>> openMpThreadBuffers(
        simulatedThreadBuffers,
        std::vector<double>(vertexCount * kProductionForceComponentsPerVertex, 0.0));

    for (int contribution = 0;
         contribution < static_cast<int>(contributionScales.size());
         ++contribution)
    {
        const double scale = contributionScales[contribution];
        add_rows_to_production_force_buffer(serial,
                                            faceOneRing,
                                            fBendRows,
                                            fAreaRows,
                                            fVolumeRows,
                                            scale);
        add_rows_to_production_force_buffer(
            openMpThreadBuffers[contribution % simulatedThreadBuffers],
            faceOneRing,
            fBendRows,
            fAreaRows,
            fVolumeRows,
            scale);
    }

    std::vector<double> openMpReduced(vertexCount * kProductionForceComponentsPerVertex, 0.0);
    for (int vertex = 0; vertex < vertexCount; ++vertex)
    {
        const int baseIndex = vertex * kProductionForceComponentsPerVertex;
        for (int component = 0; component < kProductionForceComponentsPerVertex;
             ++component)
        {
            for (int threadIndex = 0; threadIndex < simulatedThreadBuffers;
                 ++threadIndex)
            {
                openMpReduced[baseIndex + component] +=
                    openMpThreadBuffers[threadIndex][baseIndex + component];
            }
        }
    }

    AccumulationParityResult result;
    result.simulatedFaceContributions =
        static_cast<int>(contributionScales.size());
    result.simulatedOpenMpThreadBuffers = simulatedThreadBuffers;
    result.maxDifference = max_abs_component_delta(serial, openMpReduced);
    result.maxAbsSerialComponent = max_abs_component(serial);
    result.finite = all_finite(serial) && all_finite(openMpReduced);
    result.nonzero = result.maxAbsSerialComponent > kTolerance;
    result.matchesSerialOpenMpShape =
        result.finite && result.nonzero && result.maxDifference <= kTolerance;
    return result;
}

OpenSubdivRegularProductionParityRecheck
run_regular_production_route_policy_diagnostic()
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
    }

    for (Vertex &vertex : mesh.vertices)
    {
        const double index = static_cast<double>(vertex.index);
        vertex.coord.set(2,
                         0,
                         0.03 * std::sin(0.7 * index) +
                             0.01 * std::cos(0.3 * index));
    }
    mesh.calculate_element_area_volume();
    mesh.sum_membrane_area_and_volume(mesh.param.area, mesh.param.vol);

    OpenSubdivRegularProductionParityRecheck recheck;
    {
        ScopedEnvVar runtimeOptIn("SLIMED_USE_OPENSUBDIV_REGULAR", "1");
        ScopedCoutSilencer silence;
        recheck = diagnose_opensubdiv_regular_production_call_parity(mesh);
    }
    return recheck;
}

ProductionDryRunResult run_regular_production_helper_dry_run(
    const MeshCase &mesh,
    const std::vector<int> &faceOneRing,
    const std::vector<WeightedSampleProof> &proofs,
    const std::array<RegularSample, 3> &samples,
    const ActualForceParams &forceParams,
    const ActualForceResult &proofLocalResult)
{
    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Periodic;
    param.kCurv = forceParams.kCurv;
    param.uSurf = forceParams.uSurf;
    param.uVol = forceParams.uVol;
    param.area0 = forceParams.area0;
    param.vol0 = forceParams.vol0;

    Mesh productionMesh(param);
    productionMesh.param.shapeFunctions.clear();
    productionMesh.param.shapeFunctions.reserve(proofs.size());
    productionMesh.param.gaussQuadratureCoeff =
        Matrix(static_cast<int>(samples.size()), 1, true);
    for (int sampleIndex = 0; sampleIndex < static_cast<int>(proofs.size());
         ++sampleIndex)
    {
        productionMesh.param.shapeFunctions.push_back(
            make_shape_function_matrix(proofs[sampleIndex]));
        productionMesh.param.gaussQuadratureCoeff.set(sampleIndex,
                                                      0,
                                                      samples[sampleIndex].weight);
    }
    productionMesh.param.area = forceParams.area;
    productionMesh.param.vol = forceParams.vol;

    Face face;
    face.index = mesh.sampleFace;
    face.oneRingVertices = faceOneRing;
    face.spontCurvature = forceParams.spontCurv;

    Matrix normVector = mat_calloc(3, 1);
    Matrix fBend = mat_calloc(kProductionRegularControlPointCount,
                              kProductionSpatialDimension);
    Matrix fArea = mat_calloc(kProductionRegularControlPointCount,
                              kProductionSpatialDimension);
    Matrix fVolume = mat_calloc(kProductionRegularControlPointCount,
                                kProductionSpatialDimension);

    ProductionDryRunResult result;
    productionMesh.element_energy_force_regular(
        make_production_coordinate_columns(mesh, faceOneRing),
        face,
        face.spontCurvature,
        result.meanCurv,
        normVector,
        result.eBend,
        fBend,
        fArea,
        fVolume,
        false);

    append_matrix_rows(fBend, result.fBend);
    append_matrix_rows(fArea, result.fArea);
    append_matrix_rows(fVolume, result.fVolume);
    result.normVector = make_vec_from_column(normVector);

    std::vector<double> proofLocalBendRows;
    std::vector<double> proofLocalAreaRows;
    std::vector<double> proofLocalVolumeRows;
    proofLocalBendRows.reserve(result.fBend.size());
    proofLocalAreaRows.reserve(result.fArea.size());
    proofLocalVolumeRows.reserve(result.fVolume.size());
    for (int row = 0; row < static_cast<int>(faceOneRing.size()); ++row)
    {
        const int sourceId = faceOneRing[row];
        for (int axis = 0; axis < kProductionSpatialDimension; ++axis)
        {
            proofLocalBendRows.push_back(
                proofLocalResult.fBend[3 * sourceId + axis]);
            proofLocalAreaRows.push_back(
                proofLocalResult.fArea[3 * sourceId + axis]);
            proofLocalVolumeRows.push_back(
                proofLocalResult.fVolume[3 * sourceId + axis]);
        }
    }

    result.maxForceRowDifference =
        std::max(max_abs_component_delta(result.fBend, proofLocalBendRows),
                 std::max(max_abs_component_delta(result.fArea,
                                                  proofLocalAreaRows),
                          max_abs_component_delta(result.fVolume,
                                                  proofLocalVolumeRows)));
    const std::array<double, 3> productionNormal = {
        result.normVector.x,
        result.normVector.y,
        result.normVector.z};
    const std::array<double, 3> proofLocalNormal = {
        proofLocalResult.normVector.x,
        proofLocalResult.normVector.y,
        proofLocalResult.normVector.z};
    result.maxScalarDifference =
        std::max(max_abs_scalar_delta(result.meanCurv,
                                      proofLocalResult.meanCurv),
                 std::max(max_abs_scalar_delta(result.eBend,
                                               proofLocalResult.eBend),
                          max_abs_delta(productionNormal, proofLocalNormal)));
    result.finite =
        all_finite(result.fBend) && all_finite(result.fArea) &&
        all_finite(result.fVolume) && std::isfinite(result.meanCurv) &&
        std::isfinite(result.eBend) && finite_vec(result.normVector);
    result.matchesProofLocalRows =
        result.finite &&
        result.maxForceRowDifference <= kTolerance &&
        result.maxScalarDifference <= kTolerance;
    return result;
}

VisibleObservableResult run_regular_visible_observable_dry_run(
    const MeshCase &mesh,
    const std::vector<int> &faceOneRing,
    const std::vector<WeightedSampleProof> &proofs,
    const std::array<RegularSample, 3> &samples)
{
    VisibleObservableResult result;
    for (int sampleIndex = 0; sampleIndex < static_cast<int>(proofs.size());
         ++sampleIndex)
    {
        accumulate_visible_observable_sample(proofs[sampleIndex],
                                             samples[sampleIndex].weight,
                                             result);
    }

    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Periodic;
    Mesh productionMesh(param);
    productionMesh.param.shapeFunctions.clear();
    productionMesh.param.shapeFunctions.reserve(proofs.size());
    productionMesh.param.gaussQuadratureCoeff =
        Matrix(static_cast<int>(samples.size()), 1, true);
    for (int sampleIndex = 0; sampleIndex < static_cast<int>(proofs.size());
         ++sampleIndex)
    {
        productionMesh.param.shapeFunctions.push_back(
            make_shape_function_matrix(proofs[sampleIndex]));
        productionMesh.param.gaussQuadratureCoeff.set(sampleIndex,
                                                      0,
                                                      samples[sampleIndex].weight);
    }

    productionMesh.vertices.reserve(mesh.points.size());
    for (int vertexIndex = 0; vertexIndex < static_cast<int>(mesh.points.size());
         ++vertexIndex)
    {
        const Point &point = mesh.points[vertexIndex];
        productionMesh.vertices.emplace_back(vertexIndex, point.x, point.y, point.z);
    }
    productionMesh.faces.emplace_back();
    Face &face = productionMesh.faces.back();
    face.index = mesh.sampleFace;
    face.oneRingVertices = faceOneRing;
    face.isGhost = false;
    productionMesh.calculate_element_area_volume();

    result.productionArea = productionMesh.faces.front().elementArea;
    result.productionLegacyVisibleVolume =
        productionMesh.faces.front().elementVolume;
    result.maxAreaVolumeDifference =
        std::max(std::abs(result.area - result.productionArea),
                 std::abs(result.legacyVisibleVolume -
                          result.productionLegacyVisibleVolume));
    result.finite = std::isfinite(result.area) &&
                    std::isfinite(result.fullDotVolume) &&
                    std::isfinite(result.legacyVisibleVolume) &&
                    std::isfinite(result.productionArea) &&
                    std::isfinite(result.productionLegacyVisibleVolume);
    result.matchesProductionAreaVolume =
        result.finite && result.maxAreaVolumeDifference <= kTolerance;
    return result;
}

int run_proof()
{
    const MeshCase mesh = make_regular_lattice_case();
    Far::TopologyRefiner *refiner = create_refiner(mesh);
    if (!refiner)
    {
        std::cerr << "failed to create OpenSubdiv topology refiner\n";
        return 2;
    }
    Far::TopologyRefiner::AdaptiveOptions adaptiveOptions(3);
    refiner->RefineAdaptive(adaptiveOptions);

    const std::array<RegularSample, 3> samples = frozen_regular_samples();
    float s[3] = {static_cast<float>(samples[0].v),
                  static_cast<float>(samples[1].v),
                  static_cast<float>(samples[2].v)};
    float t[3] = {static_cast<float>(samples[0].w),
                  static_cast<float>(samples[1].w),
                  static_cast<float>(samples[2].w)};

    Far::LimitStencilTableFactory::LocationArray location;
    location.ptexIdx = mesh.sampleFace;
    location.numLocations = static_cast<int>(samples.size());
    location.s = s;
    location.t = t;

    Far::LimitStencilTableFactory::LocationArrayVec locations;
    locations.push_back(location);

    Far::LimitStencilTableFactory::Options stencilOptions;
    stencilOptions.generate1stDerivatives = true;
    stencilOptions.generate2ndDerivatives = true;
    const Far::LimitStencilTable *stencils =
        Far::LimitStencilTableFactory::Create(*refiner, locations, 0, 0,
                                              stencilOptions);
    if (!stencils)
    {
        delete refiner;
        std::cerr << "failed to create OpenSubdiv limit stencils\n";
        return 3;
    }

    const std::vector<int> faceOneRing =
        regular_lattice_face_one_ring_source_ids();
    std::vector<int> duplicateSourceIds = faceOneRing;
    duplicateSourceIds[1] = duplicateSourceIds[0];
    duplicateSourceIds[4] = duplicateSourceIds[3];
    duplicateSourceIds[8] = duplicateSourceIds[7];

    double maxAdapterVsStencil = 0.0;
    double maxDuplicateAggregation = 0.0;
    bool allSourcesMatchFaceOneRing = true;
    bool allMixedRowsDuplicated = true;
    bool allProofSourceOrdersMatchFaceOneRing = true;
    ActualForceParams forceParams;
    std::vector<WeightedSampleProof> proofs;
    proofs.reserve(stencils->GetNumStencils());

    std::cout << std::setprecision(12);
    std::cout << "{";
    std::cout << "\"kind\":\"test_only_regular_opensubdiv_cpp_adapter_proof\"";
    std::cout << ",\"not_production_routing\":true";
    std::cout << ",\"proof_boundary\":\"experimental C++ harness compiled only by explicit OPENSUBDIV_ROOT wrapper\"";
    std::cout << ",\"contract\":\"LimitSurfaceWeightedSample-style seven rows keyed by original SLIMED source ids\"";
    std::cout << ",\"source_id_policy\":\"original_slimed_vertex_ids_not_backend_local_ids\"";
    std::cout << ",\"sample_set\":\"frozen_regular_second_order_triangular_quadrature\"";
    std::cout << ",\"coordinate_mapping\":\"s=v,t=w\"";
    std::cout << ",\"row_order\":\"position,d/dv,d/dw,d2/dv2,d2/dw2,d2/dvdw,d2/dwdv\"";
    std::cout << ",\"mixed_derivative_policy\":\"OpenSubdiv duv duplicated into MixedDerivativeVW and MixedDerivativeWV\"";
    std::cout << ",\"face_one_ring_source_ids\":";
    print_int_vector(faceOneRing);
    std::cout << ",\"duplicate_aggregation_probe_source_ids\":";
    print_int_vector(duplicateSourceIds);
    std::cout << ",\"samples\":[";

    for (int sampleIndex = 0; sampleIndex < stencils->GetNumStencils();
         ++sampleIndex)
    {
        Far::LimitStencil stencil = stencils->GetLimitStencil(sampleIndex);
        WeightedSampleProof proof =
            adapt_regular_sample(mesh, stencil, faceOneRing);
        proofs.push_back(proof);
        allProofSourceOrdersMatchFaceOneRing =
            allProofSourceOrdersMatchFaceOneRing &&
            (proof.sourceIds == faceOneRing);
        accumulate_area_volume(proof, samples[sampleIndex].weight, forceParams);

        const std::array<const float *, 7> rowPtrs = {
            stencil.GetWeights(),
            stencil.GetDuWeights(),
            stencil.GetDvWeights(),
            stencil.GetDuuWeights(),
            stencil.GetDvvWeights(),
            stencil.GetDuvWeights(),
            stencil.GetDuvWeights(),
        };

        double sampleMaxAdapterVsStencil = 0.0;
        double sampleMaxDuplicateAggregation = 0.0;
        for (int row = 0; row < 7; ++row)
        {
            const std::array<double, 3> stencilRow =
                evaluate_row_by_stencil_order(mesh, stencil, rowPtrs[row]);
            sampleMaxAdapterVsStencil =
                std::max(sampleMaxAdapterVsStencil,
                         max_abs_delta(proof.evaluatedRows[row], stencilRow));

            WeightedSampleProof duplicateProof = proof;
            duplicateProof.sourceIds = duplicateSourceIds;
            const double actualDuplicate =
                duplicateProof.row_weight(static_cast<WeightedRow>(row),
                                          duplicateSourceIds[0]);
            const double expectedDuplicate =
                proof.rowWeights[row][0] + proof.rowWeights[row][1];
            sampleMaxDuplicateAggregation =
                std::max(sampleMaxDuplicateAggregation,
                         std::abs(actualDuplicate - expectedDuplicate));
        }

        const std::set<int> stencilSources = stencil_source_set(stencil);
        const bool sourcesMatch = same_set(stencilSources, faceOneRing);
        const bool mixedRowsDuplicated =
            rows_equal(proof.rowWeights[static_cast<int>(WeightedRow::MixedDerivativeVW)],
                       proof.rowWeights[static_cast<int>(WeightedRow::MixedDerivativeWV)]);

        allSourcesMatchFaceOneRing = allSourcesMatchFaceOneRing && sourcesMatch;
        allMixedRowsDuplicated = allMixedRowsDuplicated && mixedRowsDuplicated;
        maxAdapterVsStencil =
            std::max(maxAdapterVsStencil, sampleMaxAdapterVsStencil);
        maxDuplicateAggregation =
            std::max(maxDuplicateAggregation, sampleMaxDuplicateAggregation);

        if (sampleIndex > 0)
        {
            std::cout << ",";
        }
        const RegularSample &sample = samples[sampleIndex];
        std::cout << "{";
        std::cout << "\"index\":" << sampleIndex;
        std::cout << ",\"v\":" << sample.v;
        std::cout << ",\"w\":" << sample.w;
        std::cout << ",\"u\":" << sample.u;
        std::cout << ",\"s\":" << sample.v;
        std::cout << ",\"t\":" << sample.w;
        std::cout << ",\"quadrature_weight\":" << sample.weight;
        std::cout << ",\"formula_factor\":" << 0.5 * sample.weight;
        std::cout << ",\"adapter_row_count\":7";
        std::cout << ",\"adapter_column_count\":" << proof.sourceIds.size();
        std::cout << ",\"stencil_source_ids\":";
        print_int_set(stencilSources);
        std::cout << ",\"stencil_sources_match_face_one_ring\":"
                  << (sourcesMatch ? "true" : "false");
        std::cout << ",\"mixed_rows_duplicated\":"
                  << (mixedRowsDuplicated ? "true" : "false");
        std::cout << ",\"max_adapter_vs_stencil_eval_difference\":"
                  << sampleMaxAdapterVsStencil;
        std::cout << ",\"max_duplicate_aggregation_difference\":"
                  << sampleMaxDuplicateAggregation;
        std::cout << "}";
    }

    const DoubleLimitStencilFeasibilityResult doubleLimitStencil =
        evaluate_double_limit_stencil_feasibility(mesh,
                                                  *refiner,
                                                  faceOneRing,
                                                  samples,
                                                  proofs);

    ActualForceResult forceResult;
    forceResult.fBend.assign(mesh.numVertices * 3, 0.0);
    forceResult.fArea.assign(mesh.numVertices * 3, 0.0);
    forceResult.fVolume.assign(mesh.numVertices * 3, 0.0);
    std::set<int> forceSourceIds;
    bool finiteForceRows = true;
    for (int sampleIndex = 0; sampleIndex < static_cast<int>(proofs.size());
         ++sampleIndex)
    {
        finiteForceRows =
            accumulate_actual_force_sample(proofs[sampleIndex],
                                           samples[sampleIndex].weight,
                                           forceParams,
                                           forceResult,
                                           forceSourceIds) &&
            finiteForceRows;
    }
    forceResult.normVector = normalized(forceResult.normVector);

    const bool forceComponentsFinite =
        all_finite(forceResult.fBend) && all_finite(forceResult.fArea) &&
        all_finite(forceResult.fVolume) && std::isfinite(forceResult.eBend) &&
        std::isfinite(forceResult.meanCurv) && finite_vec(forceResult.normVector);
    const double bendMax = max_abs_component(forceResult.fBend);
    const double areaMax = max_abs_component(forceResult.fArea);
    const double volumeMax = max_abs_component(forceResult.fVolume);
    const bool nonzeroActualForce =
        bendMax > kTolerance && areaMax > kTolerance && volumeMax > kTolerance;
    const bool forceSourcesMatchFaceOneRing =
        same_set(forceSourceIds, faceOneRing);

    const ProductionDryRunResult productionDryRun =
        run_regular_production_helper_dry_run(mesh,
                                              faceOneRing,
                                              proofs,
                                              samples,
                                              forceParams,
                                              forceResult);
    const VisibleObservableResult visibleObservables =
        run_regular_visible_observable_dry_run(mesh, faceOneRing, proofs, samples);
    const OpenSubdivRegularProductionParityRecheck productionRoutePolicy =
        run_regular_production_route_policy_diagnostic();

    std::vector<double> proofLocalBendRows(faceOneRing.size() * kProductionSpatialDimension, 0.0);
    std::vector<double> proofLocalAreaRows(faceOneRing.size() * kProductionSpatialDimension, 0.0);
    std::vector<double> proofLocalVolumeRows(faceOneRing.size() * kProductionSpatialDimension, 0.0);
    std::vector<double> scatteredBend(mesh.numVertices * 3, 0.0);
    std::vector<double> scatteredArea(mesh.numVertices * 3, 0.0);
    std::vector<double> scatteredVolume(mesh.numVertices * 3, 0.0);
    std::vector<double> productionCallShadowBuffer(
        mesh.numVertices * kProductionForceComponentsPerVertex, 0.0);
    for (int row = 0; row < static_cast<int>(faceOneRing.size()); ++row)
    {
        const int sourceId = faceOneRing[row];
        for (int axis = 0; axis < 3; ++axis)
        {
            proofLocalBendRows[kProductionSpatialDimension * row + axis] =
                forceResult.fBend[3 * sourceId + axis];
            proofLocalAreaRows[kProductionSpatialDimension * row + axis] =
                forceResult.fArea[3 * sourceId + axis];
            proofLocalVolumeRows[kProductionSpatialDimension * row + axis] =
                forceResult.fVolume[3 * sourceId + axis];
            scatteredBend[3 * sourceId + axis] =
                forceResult.fBend[3 * sourceId + axis];
            scatteredArea[3 * sourceId + axis] =
                forceResult.fArea[3 * sourceId + axis];
            scatteredVolume[3 * sourceId + axis] =
                forceResult.fVolume[3 * sourceId + axis];
            const int baseIndex = sourceId * kProductionForceComponentsPerVertex;
            productionCallShadowBuffer[baseIndex + axis] +=
                proofLocalBendRows[kProductionSpatialDimension * row + axis];
            productionCallShadowBuffer[baseIndex + 3 + axis] +=
                proofLocalAreaRows[kProductionSpatialDimension * row + axis];
            productionCallShadowBuffer[baseIndex + 6 + axis] +=
                proofLocalVolumeRows[kProductionSpatialDimension * row + axis];
        }
    }
    const AccumulationParityResult accumulationParity =
        run_serial_openmp_accumulation_parity_proof(
            mesh.numVertices,
            faceOneRing,
            proofLocalBendRows,
            proofLocalAreaRows,
            proofLocalVolumeRows);
    const double scatterDifference =
        std::max(max_abs_component_delta(scatteredBend, forceResult.fBend),
                 std::max(max_abs_component_delta(scatteredArea,
                                                  forceResult.fArea),
                          max_abs_component_delta(scatteredVolume,
                                                  forceResult.fVolume)));
    const double productionShadowScatterDifference =
        max_production_scatter_delta(productionCallShadowBuffer,
                                     forceResult.fBend,
                                     forceResult.fArea,
                                     forceResult.fVolume);
    const bool productionCallShadowPassed =
        allProofSourceOrdersMatchFaceOneRing &&
        faceOneRing.size() == kProductionRegularControlPointCount &&
        kProductionDerivativeRowCount == 7 &&
        kProductionSpatialDimension == 3 &&
        kProductionForceComponentsPerVertex == 9 &&
        productionShadowScatterDifference <= kTolerance;

    const bool adapterRowsPassed =
        allSourcesMatchFaceOneRing && allMixedRowsDuplicated &&
        maxAdapterVsStencil <= kTolerance && maxDuplicateAggregation == 0.0;
    const bool actualForceRowsPassed =
        finiteForceRows && forceComponentsFinite && nonzeroActualForce &&
        forceSourcesMatchFaceOneRing && scatterDifference <= kTolerance;
    const bool productionRoutePolicyPassed =
        productionRoutePolicy.opensubdivCompiled &&
        productionRoutePolicy.runtimeOptInRequested &&
        productionRoutePolicy.productionRouteEnabled &&
        productionRoutePolicy.routeInstalledInProduction &&
        productionRoutePolicy.generatedRoutedRows &&
        productionRoutePolicy.comparedFaceCount > 0 &&
        productionRoutePolicy.directRowsOverrideMatch &&
        productionRoutePolicy.directVsRoutedMatch &&
        !productionRoutePolicy.routedResidualsExceedCurrentTolerance &&
        !productionRoutePolicy.routedResidualToleranceReviewRequired &&
        productionRoutePolicy.routedResidualCurrentPolicySatisfied &&
        productionRoutePolicy.routedResidualActivationAllowedByCurrentPolicy &&
        productionRoutePolicy.routedResidualReadinessDecision ==
            "guarded_route_active" &&
        productionRoutePolicy.routedResidualActivationBlocker == "none" &&
        productionRoutePolicy.routedResidualActivationPolicyDecision ==
            "current_policy_satisfied_route_active";
    const bool doubleLimitStencilDiagnosticPassed =
        doubleLimitStencil.stencilTableCreated &&
        doubleLimitStencil.stencilSourcesMatchFaceOneRing &&
        doubleLimitStencil.mixedRowsDuplicated &&
        doubleLimitStencil.sampleCount == static_cast<int>(samples.size()) &&
        doubleLimitStencil.doubleRowsMatchSlimedAtStrictPrecision;
    const bool passed =
        adapterRowsPassed && actualForceRowsPassed && productionCallShadowPassed &&
        productionDryRun.matchesProofLocalRows &&
        visibleObservables.matchesProductionAreaVolume &&
        accumulationParity.matchesSerialOpenMpShape &&
        productionRoutePolicyPassed && doubleLimitStencilDiagnosticPassed;

    std::cout << "]";
    std::cout << ",\"summary\":{";
    std::cout << "\"sample_count\":" << stencils->GetNumStencils();
    std::cout << ",\"all_stencil_sources_match_face_one_ring\":"
              << (allSourcesMatchFaceOneRing ? "true" : "false");
    std::cout << ",\"all_mixed_rows_duplicated\":"
              << (allMixedRowsDuplicated ? "true" : "false");
    std::cout << ",\"max_adapter_vs_stencil_eval_difference\":"
              << maxAdapterVsStencil;
    std::cout << ",\"max_duplicate_aggregation_difference\":"
              << maxDuplicateAggregation;
    std::cout << ",\"tolerance\":" << kTolerance;
    std::cout << ",\"passed\":"
              << (adapterRowsPassed ? "true" : "false");
    std::cout << "}";
    std::cout << ",\"double_limit_stencil_feasibility\":{";
    std::cout << "\"scope\":\"proof-only comparison of OpenSubdiv double limit-stencil rows against current float limit-stencil rows and frozen SLIMED double rows\"";
    std::cout << ",\"not_production_routing\":true";
    std::cout << ",\"production_route_enabled\":false";
    std::cout << ",\"route_installed_in_production\":false";
    std::cout << ",\"tolerance_policy_changed\":false";
    std::cout << ",\"stencil_table_created\":"
              << (doubleLimitStencil.stencilTableCreated ? "true" : "false");
    std::cout << ",\"stencil_sources_match_face_one_ring\":"
              << (doubleLimitStencil.stencilSourcesMatchFaceOneRing ? "true" : "false");
    std::cout << ",\"mixed_rows_duplicated\":"
              << (doubleLimitStencil.mixedRowsDuplicated ? "true" : "false");
    std::cout << ",\"sample_count\":" << doubleLimitStencil.sampleCount;
    std::cout << ",\"max_float_limit_stencil_vs_slimed_row_difference\":"
              << doubleLimitStencil.maxFloatStencilVsSlimedRowDifference;
    std::cout << ",\"max_double_limit_stencil_vs_slimed_row_difference\":"
              << doubleLimitStencil.maxDoubleStencilVsSlimedRowDifference;
    std::cout << ",\"max_double_vs_float_limit_stencil_difference\":"
              << doubleLimitStencil.maxDoubleStencilVsFloatStencilDifference;
    std::cout << ",\"strict_precision_tolerance\":1e-12";
    std::cout << ",\"double_rows_match_slimed_at_strict_precision\":"
              << (doubleLimitStencil.doubleRowsMatchSlimedAtStrictPrecision ? "true" : "false");
    std::cout << ",\"diagnostic_passed\":"
              << (doubleLimitStencilDiagnosticPassed ? "true" : "false");
    std::cout << "}";
    std::cout << ",\"production_call_shadow\":{";
    std::cout << "\"scope\":\"proof-local shadow of the current regular production call shape; no production route invokes OpenSubdiv\"";
    std::cout << ",\"not_production_routing\":true";
    std::cout << ",\"regular_control_point_count\":"
              << kProductionRegularControlPointCount;
    std::cout << ",\"input_coordinate_columns\":\"coordOneRingVertices[j] copied from Face::oneRingVertices[j]\"";
    std::cout << ",\"input_source_ids\":";
    print_int_vector(faceOneRing);
    std::cout << ",\"weighted_sample_source_order_matches_input\":"
              << (allProofSourceOrdersMatchFaceOneRing ? "true" : "false");
    std::cout << ",\"derivative_row_count\":"
              << kProductionDerivativeRowCount;
    std::cout << ",\"local_force_matrix_rows\":"
              << faceOneRing.size();
    std::cout << ",\"local_force_matrix_columns\":"
              << kProductionSpatialDimension;
    std::cout << ",\"force_components_per_vertex\":"
              << kProductionForceComponentsPerVertex;
    std::cout << ",\"scatter_layout\":\"fBend offsets 0..2, fArea offsets 3..5, fVolume offsets 6..8\"";
    std::cout << ",\"local_row_to_vertex_scatter\":\"row j -> Face::oneRingVertices[j]\"";
    std::cout << ",\"shadow_scatter_max_abs_difference\":"
              << productionShadowScatterDifference;
    std::cout << ",\"matches_current_regular_production_call_shape\":"
              << (productionCallShadowPassed ? "true" : "false");
    std::cout << "}";
    std::cout << ",\"production_helper_dry_run\":{";
    std::cout << "\"scope\":\"proof-local call to current Mesh::element_energy_force_regular with OpenSubdiv-derived regular rows installed only on a local Param\"";
    std::cout << ",\"not_production_routing\":true";
    std::cout << ",\"production_api\":\"Mesh::element_energy_force_regular\"";
    std::cout << ",\"open_subdiv_rows_used_as_local_shape_functions\":true";
    std::cout << ",\"default_build_dependency_added\":false";
    std::cout << ",\"route_installed_in_production\":false";
    std::cout << ",\"regular_control_point_count\":"
              << kProductionRegularControlPointCount;
    std::cout << ",\"sample_count\":" << proofs.size();
    std::cout << ",\"gauss_coefficients_source\":\"frozen OpenSubdiv regular sample plan weights\"";
    std::cout << ",\"spontaneous_curvature\":" << forceParams.spontCurv;
    std::cout << ",\"area\":" << forceParams.area;
    std::cout << ",\"volume\":" << forceParams.vol;
    std::cout << ",\"mean_curvature\":" << productionDryRun.meanCurv;
    std::cout << ",\"e_bend\":" << productionDryRun.eBend;
    std::cout << ",\"normal\":";
    print_vec3(productionDryRun.normVector);
    std::cout << ",\"max_force_row_difference_vs_proof_local_formula\":"
              << productionDryRun.maxForceRowDifference;
    std::cout << ",\"max_scalar_difference_vs_proof_local_formula\":"
              << productionDryRun.maxScalarDifference;
    std::cout << ",\"finite\":" << (productionDryRun.finite ? "true" : "false");
    std::cout << ",\"matches_proof_local_formula_rows\":"
              << (productionDryRun.matchesProofLocalRows ? "true" : "false");
    std::cout << "}";
    std::cout << ",\"visible_observable_dry_run\":{";
    std::cout << "\"scope\":\"proof-local regular area/volume observable comparison using OpenSubdiv-derived rows on a local Param only\"";
    std::cout << ",\"not_production_routing\":true";
    std::cout << ",\"production_api\":\"Mesh::calculate_element_area_volume regular 12-control path\"";
    std::cout << ",\"open_subdiv_rows_used_as_local_shape_functions\":true";
    std::cout << ",\"default_build_dependency_added\":false";
    std::cout << ",\"route_installed_in_production\":false";
    std::cout << ",\"regular_control_point_count\":"
              << kProductionRegularControlPointCount;
    std::cout << ",\"sample_count\":" << proofs.size();
    std::cout << ",\"area\":" << visibleObservables.area;
    std::cout << ",\"production_area\":"
              << visibleObservables.productionArea;
    std::cout << ",\"legacy_visible_volume\":"
              << visibleObservables.legacyVisibleVolume;
    std::cout << ",\"production_legacy_visible_volume\":"
              << visibleObservables.productionLegacyVisibleVolume;
    std::cout << ",\"force_fixture_full_dot_volume\":"
              << visibleObservables.fullDotVolume;
    std::cout << ",\"volume_note\":\"legacy visible volume preserves current regular area/volume x-component quadrature behavior; force fixture volume remains separately reported\"";
    std::cout << ",\"max_area_volume_difference_vs_production_regular_path\":"
              << visibleObservables.maxAreaVolumeDifference;
    std::cout << ",\"finite\":"
              << (visibleObservables.finite ? "true" : "false");
    std::cout << ",\"matches_production_regular_area_volume\":"
              << (visibleObservables.matchesProductionAreaVolume ? "true" : "false");
    std::cout << "}";
    std::cout << ",\"serial_openmp_accumulation_parity\":{";
    std::cout << "\"scope\":\"proof-local serial versus OpenMP-style per-thread force-buffer accumulation using OpenSubdiv-derived regular rows; no production route invokes OpenSubdiv\"";
    std::cout << ",\"not_production_routing\":true";
    std::cout << ",\"production_shape_reference\":\"accumulate_membrane_face_energy_and_forces per-thread nVertices*9 buffers reduced by vertex, component, then thread index\"";
    std::cout << ",\"source_rows\":\"proof-local fBend/fArea/fVolume rows from OpenSubdiv-derived regular weighted samples\"";
    std::cout << ",\"scatter_order\":\"Face::oneRingVertices[j]\"";
    std::cout << ",\"force_components_per_vertex\":"
              << kProductionForceComponentsPerVertex;
    std::cout << ",\"simulated_face_contributions\":"
              << accumulationParity.simulatedFaceContributions;
    std::cout << ",\"simulated_openmp_thread_buffers\":"
              << accumulationParity.simulatedOpenMpThreadBuffers;
    std::cout << ",\"default_build_dependency_added\":false";
    std::cout << ",\"route_installed_in_production\":false";
    std::cout << ",\"max_serial_openmp_accumulation_difference\":"
              << accumulationParity.maxDifference;
    std::cout << ",\"max_abs_serial_component\":"
              << accumulationParity.maxAbsSerialComponent;
    std::cout << ",\"finite\":"
              << (accumulationParity.finite ? "true" : "false");
    std::cout << ",\"nonzero_accumulation\":"
              << (accumulationParity.nonzero ? "true" : "false");
    std::cout << ",\"matches_serial_openmp_accumulation_shape\":"
              << (accumulationParity.matchesSerialOpenMpShape ? "true" : "false");
    std::cout << "}";
    std::cout << ",\"production_route_policy_diagnostic\":{";
    std::cout << "\"scope\":\"opt-in diagnostic call to the guarded regular OpenSubdiv production route parity recheck\"";
    std::cout << ",\"not_production_routing\":false";
    std::cout << ",\"production_api\":\"diagnose_opensubdiv_regular_production_call_parity\"";
    std::cout << ",\"runtime_opt_in_requested\":"
              << (productionRoutePolicy.runtimeOptInRequested ? "true" : "false");
    std::cout << ",\"production_route_enabled\":"
              << (productionRoutePolicy.productionRouteEnabled ? "true" : "false");
    std::cout << ",\"route_installed_in_production\":"
              << (productionRoutePolicy.routeInstalledInProduction ? "true" : "false");
    std::cout << ",\"generated_routed_rows\":"
              << (productionRoutePolicy.generatedRoutedRows ? "true" : "false");
    std::cout << ",\"compared_face_count\":"
              << productionRoutePolicy.comparedFaceCount;
    std::cout << ",\"compared_sample_count\":"
              << productionRoutePolicy.comparedSampleCount;
    std::cout << ",\"direct_rows_override_match\":"
              << (productionRoutePolicy.directRowsOverrideMatch ? "true" : "false");
    std::cout << ",\"direct_vs_routed_match\":"
              << (productionRoutePolicy.directVsRoutedMatch ? "true" : "false");
    std::cout << ",\"max_routed_row_weight_difference_vs_slimed_rows\":"
              << productionRoutePolicy.maxRoutedRowWeightDifferenceVsSlimedRows;
    std::cout << ",\"max_f_area_difference\":"
              << productionRoutePolicy.maxFAreaDifference;
    std::cout << ",\"max_f_area_difference_relative_to_component_scale\":"
              << productionRoutePolicy.maxFAreaDifferenceRelativeToComponentScale;
    std::cout << ",\"max_f_volume_difference\":"
              << productionRoutePolicy.maxFVolumeDifference;
    std::cout << ",\"max_f_volume_difference_relative_to_component_scale\":"
              << productionRoutePolicy.maxFVolumeDifferenceRelativeToComponentScale;
    std::cout << ",\"max_scatter_difference\":"
              << productionRoutePolicy.maxScatterDifference;
    std::cout << ",\"max_scatter_difference_relative_to_component_scale\":"
              << productionRoutePolicy.maxScatterDifferenceRelativeToComponentScale;
    std::cout << ",\"routed_residual_current_absolute_tolerance\":"
              << productionRoutePolicy.routedResidualCurrentAbsoluteTolerance;
    std::cout << ",\"routed_residual_required_absolute_tolerance\":"
              << productionRoutePolicy.routedResidualRequiredAbsoluteTolerance;
    std::cout << ",\"routed_residual_required_relative_tolerance\":"
              << productionRoutePolicy.routedResidualRequiredRelativeTolerance;
    std::cout << ",\"routed_residual_required_tolerance_multiplier\":"
              << productionRoutePolicy.routedResidualRequiredToleranceMultiplier;
    std::cout << ",\"routed_residual_required_tolerance_source\":\""
              << productionRoutePolicy.routedResidualRequiredToleranceSource
              << "\"";
    std::cout << ",\"routed_residual_required_tolerance_source_relative\":"
              << productionRoutePolicy.routedResidualRequiredToleranceSourceRelative;
    std::cout << ",\"routed_residuals_exceed_current_tolerance\":"
              << (productionRoutePolicy.routedResidualsExceedCurrentTolerance ? "true" : "false");
    std::cout << ",\"routed_residual_tolerance_review_required\":"
              << (productionRoutePolicy.routedResidualToleranceReviewRequired ? "true" : "false");
    std::cout << ",\"routed_residual_readiness_decision\":\""
              << productionRoutePolicy.routedResidualReadinessDecision << "\"";
    std::cout << ",\"routed_residual_activation_blocker\":\""
              << productionRoutePolicy.routedResidualActivationBlocker << "\"";
    std::cout << ",\"routed_residual_current_policy_satisfied\":"
              << (productionRoutePolicy.routedResidualCurrentPolicySatisfied ? "true" : "false");
    std::cout << ",\"routed_residual_activation_allowed_by_current_policy\":"
              << (productionRoutePolicy.routedResidualActivationAllowedByCurrentPolicy ? "true" : "false");
    std::cout << ",\"routed_residual_activation_policy_decision\":\""
              << productionRoutePolicy.routedResidualActivationPolicyDecision
              << "\"";
    std::cout << ",\"passed\":"
              << (productionRoutePolicyPassed ? "true" : "false");
    std::cout << "}";
    std::cout << ",\"actual_force_rows\":{";
    std::cout << "\"available\":true";
    std::cout << ",\"formula_scope\":\"proof-only local copy of current bending, area, and volume force sample algebra fed by adapter-remapped OpenSubdiv rows\"";
    std::cout << ",\"not_production_routing\":true";
    std::cout << ",\"force_source_ids\":";
    print_int_set(forceSourceIds);
    std::cout << ",\"force_sources_match_face_one_ring\":"
              << (forceSourcesMatchFaceOneRing ? "true" : "false");
    std::cout << ",\"face_one_ring_scatter_identity\":"
              << (scatterDifference <= kTolerance ? "true" : "false");
    std::cout << ",\"scatter_max_abs_difference\":" << scatterDifference;
    std::cout << ",\"area\":" << forceParams.area;
    std::cout << ",\"volume\":" << forceParams.vol;
    std::cout << ",\"e_bend\":" << forceResult.eBend;
    std::cout << ",\"mean_curvature\":" << forceResult.meanCurv;
    std::cout << ",\"normal\":";
    print_vec3(forceResult.normVector);
    std::cout << ",\"max_abs_f_bend\":" << bendMax;
    std::cout << ",\"max_abs_f_area\":" << areaMax;
    std::cout << ",\"max_abs_f_volume\":" << volumeMax;
    std::cout << ",\"l1_f_bend\":" << l1_component_sum(forceResult.fBend);
    std::cout << ",\"l1_f_area\":" << l1_component_sum(forceResult.fArea);
    std::cout << ",\"l1_f_volume\":" << l1_component_sum(forceResult.fVolume);
    std::cout << ",\"finite\":" << (forceComponentsFinite ? "true" : "false");
    std::cout << ",\"nonzero_actual_force\":"
              << (nonzeroActualForce ? "true" : "false");
    std::cout << ",\"rows\":[";
    for (int row = 0; row < static_cast<int>(faceOneRing.size()); ++row)
    {
        const int sourceId = faceOneRing[row];
        if (row > 0)
        {
            std::cout << ",";
        }
        std::cout << "{\"local_row\":" << row;
        std::cout << ",\"source_id\":" << sourceId;
        std::cout << ",\"f_bend\":";
        print_vec3(make_vec(forceResult.fBend[3 * sourceId],
                            forceResult.fBend[3 * sourceId + 1],
                            forceResult.fBend[3 * sourceId + 2]));
        std::cout << ",\"f_area\":";
        print_vec3(make_vec(forceResult.fArea[3 * sourceId],
                            forceResult.fArea[3 * sourceId + 1],
                            forceResult.fArea[3 * sourceId + 2]));
        std::cout << ",\"f_volume\":";
        print_vec3(make_vec(forceResult.fVolume[3 * sourceId],
                            forceResult.fVolume[3 * sourceId + 1],
                            forceResult.fVolume[3 * sourceId + 2]));
        std::cout << "}";
    }
    std::cout << "]";
    std::cout << ",\"passed\":"
              << (actualForceRowsPassed ? "true" : "false");
    std::cout << "}";
    std::cout << ",\"passed\":" << (passed ? "true" : "false");
    std::cout << "}" << std::endl;

    delete stencils;
    delete refiner;
    return passed ? 0 : 4;
}
}

int main()
{
    return run_proof();
}
