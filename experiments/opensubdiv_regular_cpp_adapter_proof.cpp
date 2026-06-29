// Experimental, review-gated OpenSubdiv regular adapter proof.
//
// This file is compiled only by scripts/run_opensubdiv_regular_cpp_adapter_proof.sh
// when OPENSUBDIV_ROOT is supplied. It is not part of default SLIMED builds.

#include <opensubdiv/far/stencilTable.h>
#include <opensubdiv/far/stencilTableFactory.h>
#include <opensubdiv/far/topologyDescriptor.h>
#include <opensubdiv/far/topologyRefinerFactory.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <set>
#include <string>
#include <vector>

using namespace OpenSubdiv;

namespace
{
constexpr double kTolerance = 5.0e-6;

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
    float v = 0.0f;
    float w = 0.0f;
    float u = 0.0f;
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

std::array<RegularSample, 3> frozen_regular_samples()
{
    return {{
        {1.0f / 6.0f, 1.0f / 6.0f, 4.0f / 6.0f, 1.0 / 3.0},
        {1.0f / 6.0f, 4.0f / 6.0f, 1.0f / 6.0f, 1.0 / 3.0},
        {4.0f / 6.0f, 1.0f / 6.0f, 1.0f / 6.0f, 1.0 / 3.0},
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
    float s[3] = {samples[0].v, samples[1].v, samples[2].v};
    float t[3] = {samples[0].w, samples[1].w, samples[2].w};

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

    const bool adapterRowsPassed =
        allSourcesMatchFaceOneRing && allMixedRowsDuplicated &&
        maxAdapterVsStencil <= kTolerance && maxDuplicateAggregation == 0.0;

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
    std::cout << ",\"passed\":" << (adapterRowsPassed ? "true" : "false");
    std::cout << "}" << std::endl;

    delete stencils;
    delete refiner;
    return adapterRowsPassed ? 0 : 4;
}
}

int main()
{
    return run_proof();
}
