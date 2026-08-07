#include <algorithm>
#include <array>
#include <cstdint>
#include <limits>
#include <type_traits>
#include <utility>
#include <vector>

#include <gtest/gtest.h>

#include "mesh/Loop_limit_surface_backend.hpp"
#include "mesh/Source_keyed_limit_rows.hpp"

namespace
{
using namespace slimed::loop_limit;

LoopTopologyKey make_valid_key()
{
    LoopTopologyKey key;
    key.topologyEpoch = 41;
    key.evaluatorApi = "bfr-surface";
    key.bfrApproxLevelSmooth = 2;
    key.bfrApproxLevelSharp = 6;
    key.bfrCacheMode = BfrCacheMode::Serial;
    key.opensubdivVersion = 30700;
    key.sourceVertexCount = 4;
    key.orientedTriangles = {
        {{0, 2, 1}},
        {{0, 1, 3}},
        {{0, 3, 2}},
        {{1, 2, 3}},
    };
    key.topologyPolicy.boundary = LoopBoundaryPolicy::Reject;
    key.topologyPolicy.ghosts = LoopGhostPolicy::Reject;
    key.topologyPolicy.holes = LoopHolePolicy::Reject;
    key.quadraturePolicy = "proof-fixed-triangle-samples";
    return key;
}

SourceKeyedFaceLimitRows make_face(int faceId,
                                  const std::vector<int> &sourceIds)
{
    SourceKeyedFaceLimitRows face;
    face.faceId = faceId;
    SourceKeyedLimitSample sample;
    sample.u = 0.2;
    sample.v = 0.3;
    sample.weight = 0.5;
    for (int rowIndex = static_cast<int>(kLimitRowCount) - 1;
         rowIndex >= 0;
         --rowIndex)
    {
        SourceKeyedLimitRow row;
        row.kind = static_cast<LimitRowKind>(rowIndex);
        for (auto source = sourceIds.rbegin();
             source != sourceIds.rend();
             ++source)
        {
            row.coefficients.push_back(
                SourceCoefficient{
                    *source,
                    100.0 * rowIndex + static_cast<double>(*source)});
        }
        sample.rows.push_back(std::move(row));
    }
    face.samples.push_back(std::move(sample));
    return face;
}

std::vector<SourceKeyedFaceLimitRows> make_valid_faces()
{
    return {
        make_face(0, {2, 0, 1}),
        make_face(1, {0, 1, 3, 2}),
        make_face(2, {0, 3, 2}),
        make_face(3, {1, 2, 3}),
    };
}

SourceKeyedLimitRow &find_row(SourceKeyedLimitSample &sample,
                              LimitRowKind kind)
{
    const auto row = std::find_if(
        sample.rows.begin(),
        sample.rows.end(),
        [kind](const SourceKeyedLimitRow &candidate) {
            return candidate.kind == kind;
        });
    return *row;
}

template <typename Mutation>
void expect_key_rejected_without_destination_mutation(
    Mutation mutation,
    LoopContractError expectedError,
    const char *expectedMessage = nullptr)
{
    LoopTopologyKey candidate = make_valid_key();
    mutation(candidate);

    LoopTopologyKey destination = make_valid_key();
    destination.topologyEpoch = 900;
    destination.quadraturePolicy = "sentinel-destination";
    const LoopTopologyKey unchanged = destination;
    const LoopContractDiagnostic diagnostic =
        assign_validated_production_loop_topology_key(
            candidate, destination);
    EXPECT_EQ(diagnostic.error, expectedError);
    if (expectedMessage != nullptr)
    {
        EXPECT_EQ(diagnostic.message, expectedMessage);
    }
    EXPECT_EQ(destination, unchanged);
}

template <typename Mutation>
void expect_face_rejected_without_destination_mutation(
    Mutation mutation,
    LoopContractError expectedError)
{
    SourceKeyedFaceLimitRows input = make_face(0, {2, 0, 1});
    mutation(input);

    DenseFaceLimitRows destination;
    destination.faceId = 73;
    destination.unionSourceIds = {3};
    DenseLimitSampleRows sentinelSample;
    sentinelSample.weight = 9.0;
    destination.samples.push_back(sentinelSample);
    const DenseFaceLimitRows unchanged = destination;

    const LoopContractDiagnostic diagnostic =
        densify_source_keyed_face(input, 0, 4, destination);
    EXPECT_EQ(diagnostic.error, expectedError);
    EXPECT_EQ(destination.faceId, unchanged.faceId);
    EXPECT_EQ(destination.unionSourceIds, unchanged.unionSourceIds);
    ASSERT_EQ(destination.samples.size(), unchanged.samples.size());
    EXPECT_EQ(destination.samples[0].weight,
              unchanged.samples[0].weight);
}

PreparedLoopLimitRowsResult make_prepared_package()
{
    return prepare_loop_limit_rows(
        make_valid_key(), 41, make_valid_faces());
}
} // namespace

TEST(LoopLimitSurfaceContract,
     PublicHeadersCompileAsBackendNeutralCxx17Contracts)
{
    LoopTopologyKey destination;
    const LoopContractDiagnostic diagnostic =
        assign_validated_production_loop_topology_key(
            make_valid_key(), destination);
    EXPECT_TRUE(diagnostic.ok());
    EXPECT_EQ(destination.evaluatorApi, "bfr-surface");

    const PreparedLoopLimitRowsResult prepared = make_prepared_package();
    ASSERT_TRUE(prepared.ok()) << prepared.diagnostic.message;
    EXPECT_TRUE((std::is_const_v<std::remove_reference_t<
                    decltype(*prepared.package)>>));
}

TEST(LoopLimitSurfaceContract,
     ProductionKeyRejectsEvaluatorLevelsAndVersionBeforeMutation)
{
    LoopTopologyKey accepted = make_valid_key();
    accepted.bfrApproxLevelSmooth = kMinimumBfrApproximationLevel;
    accepted.bfrApproxLevelSharp = kMaximumBfrApproximationLevel;
    accepted.opensubdivVersion = 1;
    LoopTopologyKey acceptedDestination;
    ASSERT_TRUE(assign_validated_production_loop_topology_key(
                    accepted, acceptedDestination)
                    .ok());
    EXPECT_EQ(acceptedDestination.opensubdivVersion, 1);

    expect_key_rejected_without_destination_mutation(
        [](LoopTopologyKey &key) {
            key.evaluatorApi = "comparison-evaluator";
        },
        LoopContractError::UnsupportedEvaluatorApi);

    for (const int invalidLevel : {-1, 256})
    {
        expect_key_rejected_without_destination_mutation(
            [invalidLevel](LoopTopologyKey &key) {
                key.bfrApproxLevelSmooth = invalidLevel;
            },
            LoopContractError::ApproximationLevelOutOfRange);
        expect_key_rejected_without_destination_mutation(
            [invalidLevel](LoopTopologyKey &key) {
                key.bfrApproxLevelSharp = invalidLevel;
            },
            LoopContractError::ApproximationLevelOutOfRange);
    }

    expect_key_rejected_without_destination_mutation(
        [](LoopTopologyKey &key) { key.opensubdivVersion = 0; },
        LoopContractError::UnpopulatedVersion);
    expect_key_rejected_without_destination_mutation(
        [](LoopTopologyKey &key) {
            key.bfrCacheMode = BfrCacheMode::Unset;
        },
        LoopContractError::InvalidCacheMode);
    expect_key_rejected_without_destination_mutation(
        [](LoopTopologyKey &key) { key.topologyEpoch = 0; },
        LoopContractError::UnpopulatedTopologyEpoch);
    expect_key_rejected_without_destination_mutation(
        [](LoopTopologyKey &key) {
            key.topologyPolicy.ghosts = LoopGhostPolicy::Unset;
        },
        LoopContractError::InvalidTopologyPolicy);
    expect_key_rejected_without_destination_mutation(
        [](LoopTopologyKey &key) { key.quadraturePolicy.clear(); },
        LoopContractError::InvalidQuadraturePolicy);
    expect_key_rejected_without_destination_mutation(
        [](LoopTopologyKey &key) { ++key.sourceVertexCount; },
        LoopContractError::InvalidTopology);
}

TEST(LoopLimitSurfaceContract,
     ClosedManifoldIncidenceRejectsInvalidTopologyAtomically)
{
    expect_key_rejected_without_destination_mutation(
        [](LoopTopologyKey &key) {
            key.orientedTriangles.pop_back();
        },
        LoopContractError::BoundaryOrHoleEdge,
        "Loop topology contains a boundary or hole edge");

    expect_key_rejected_without_destination_mutation(
        [](LoopTopologyKey &key) {
            key.sourceVertexCount = 5;
            key.orientedTriangles.push_back({{0, 1, 4}});
        },
        LoopContractError::NonManifoldEdgeIncidence,
        "Loop topology contains an edge incident to more than two faces");

    expect_key_rejected_without_destination_mutation(
        [](LoopTopologyKey &key) {
            std::swap(key.orientedTriangles[0][1],
                      key.orientedTriangles[0][2]);
        },
        LoopContractError::InconsistentOrientation,
        "Loop topology edge incidences have inconsistent orientation");

    expect_key_rejected_without_destination_mutation(
        [](LoopTopologyKey &key) {
            key.sourceVertexCount = 7;
            const std::vector<std::array<int, 3>> secondTetrahedron{
                {{0, 5, 4}},
                {{0, 4, 6}},
                {{0, 6, 5}},
                {{4, 5, 6}},
            };
            key.orientedTriangles.insert(
                key.orientedTriangles.end(),
                secondTetrahedron.begin(),
                secondTetrahedron.end());
        },
        LoopContractError::NonManifoldVertexIncidence,
        "Loop topology vertex link contains disconnected cycles");

    expect_key_rejected_without_destination_mutation(
        [](LoopTopologyKey &key) {
            key.orientedTriangles.push_back(
                key.orientedTriangles.front());
        },
        LoopContractError::DuplicateFace,
        "Loop topology contains a duplicate oriented triangle");
}

TEST(LoopLimitSurfaceContract,
     EveryBackendOrTopologyAffectingFieldMissesPreparedIdentity)
{
    const PreparedLoopLimitRowsResult prepared = make_prepared_package();
    ASSERT_TRUE(prepared.ok()) << prepared.diagnostic.message;

    const auto expectMiss = [&prepared](LoopTopologyKey request) {
        EXPECT_FALSE(prepared_package_cache_identity_matches(
            *prepared.package, request));
        const PreparedLoopLimitRowsLookup lookup =
            lookup_prepared_loop_limit_rows(
                prepared.package, request, request.topologyEpoch);
        EXPECT_FALSE(lookup.hit());
        EXPECT_EQ(lookup.diagnostic.error,
                  LoopContractError::CacheIdentityMismatch);
    };

    LoopTopologyKey request = make_valid_key();
    request.evaluatorApi = "comparison-evaluator";
    expectMiss(request);
    request = make_valid_key();
    ++request.bfrApproxLevelSmooth;
    expectMiss(request);
    request = make_valid_key();
    ++request.bfrApproxLevelSharp;
    expectMiss(request);
    request = make_valid_key();
    request.bfrCacheMode = BfrCacheMode::Threaded;
    expectMiss(request);
    request = make_valid_key();
    ++request.opensubdivVersion;
    expectMiss(request);
    request = make_valid_key();
    std::swap(request.orientedTriangles[0][1],
              request.orientedTriangles[0][2]);
    expectMiss(request);
    request = make_valid_key();
    ++request.sourceVertexCount;
    expectMiss(request);
    request = make_valid_key();
    request.topologyPolicy.boundary = LoopBoundaryPolicy::Unset;
    expectMiss(request);
    request = make_valid_key();
    request.quadraturePolicy = "different-fixed-samples";
    expectMiss(request);

    const PreparedLoopLimitRowsLookup hit =
        lookup_prepared_loop_limit_rows(
            prepared.package, make_valid_key(), 41);
    EXPECT_TRUE(hit.hit()) << hit.diagnostic.message;
    EXPECT_EQ(hit.package.get(), prepared.package.get());
}

TEST(LoopLimitSurfaceContract,
     TopologyEpochIsMonotonicAndStalePackagesAreRejected)
{
    EXPECT_TRUE(validate_topology_epoch_transition(41, 42).ok());
    EXPECT_EQ(validate_topology_epoch_transition(41, 41).error,
              LoopContractError::InvalidTopologyEpochTransition);
    EXPECT_EQ(validate_topology_epoch_transition(41, 40).error,
              LoopContractError::InvalidTopologyEpochTransition);

    std::uint64_t nextEpoch = 700;
    EXPECT_TRUE(assign_next_topology_epoch(
                    41,
                    LoopTopologyInvalidationReason::AcceptedEdgeFlip,
                    nextEpoch)
                    .ok());
    EXPECT_EQ(nextEpoch, 42u);
    const std::uint64_t unchanged = nextEpoch;
    EXPECT_EQ(assign_next_topology_epoch(
                  std::numeric_limits<std::uint64_t>::max(),
                  LoopTopologyInvalidationReason::Remeshing,
                  nextEpoch)
                  .error,
              LoopContractError::InvalidTopologyEpochTransition);
    EXPECT_EQ(nextEpoch, unchanged);

    const PreparedLoopLimitRowsResult prepared = make_prepared_package();
    ASSERT_TRUE(prepared.ok());
    const PreparedLoopLimitRowsLookup stale =
        lookup_prepared_loop_limit_rows(
            prepared.package, make_valid_key(), 42);
    EXPECT_FALSE(stale.hit());
    EXPECT_EQ(stale.diagnostic.error,
              LoopContractError::StaleTopologyEpoch);
}

TEST(LoopLimitSurfaceContract,
     SparseRowsSupportDifferentCardinalitiesAndDeterministicDenseUnions)
{
    std::vector<SourceKeyedFaceLimitRows> faces = make_valid_faces();
    find_row(faces[0].samples[0], LimitRowKind::Position)
        .coefficients.resize(1);

    const PreparedLoopLimitRowsResult prepared = prepare_loop_limit_rows(
        make_valid_key(), 41, faces);
    ASSERT_TRUE(prepared.ok()) << prepared.diagnostic.message;
    ASSERT_EQ(prepared.package->faces().size(), 4u);
    EXPECT_EQ(prepared.package->faces()[0].unionSourceIds,
              (std::vector<int>{0, 1, 2}));
    EXPECT_EQ(prepared.package->faces()[1].unionSourceIds,
              (std::vector<int>{0, 1, 2, 3}));
    EXPECT_EQ(prepared.package->faces()[0]
                  .sparseRows.samples[0]
                  .rows[limit_row_index(LimitRowKind::Position)]
                  .coefficients.size(),
              1u);

    DenseFaceLimitRows dense;
    const LoopContractDiagnostic densified = densify_source_keyed_face(
        prepared.package->faces()[0].sparseRows, 0, 4, dense);
    ASSERT_TRUE(densified.ok()) << densified.message;
    EXPECT_EQ(dense.unionSourceIds, (std::vector<int>{0, 1, 2}));
    ASSERT_EQ(dense.samples.size(), 1u);
    EXPECT_DOUBLE_EQ(dense.samples[0].u, 0.2);
    EXPECT_DOUBLE_EQ(dense.samples[0].v, 0.3);
    EXPECT_DOUBLE_EQ(dense.samples[0].weight, 0.5);
    EXPECT_EQ(dense.samples[0]
                  .rows[limit_row_index(LimitRowKind::Position)],
              (std::vector<double>{0.0, 1.0, 0.0}));

    std::vector<double> scattered(4, 1.0);
    ASSERT_TRUE(scatter_by_original_source_ids(
                    dense.unionSourceIds,
                    {10.0, 20.0, 30.0},
                    scattered)
                    .ok());
    EXPECT_DOUBLE_EQ(scattered[0], 11.0);
    EXPECT_DOUBLE_EQ(scattered[1], 21.0);
    EXPECT_DOUBLE_EQ(scattered[2], 31.0);
    EXPECT_DOUBLE_EQ(scattered[3], 1.0);
}

TEST(LoopLimitSurfaceContract,
     MalformedRowsCoordinatesWeightsAndFaceIdsRejectAtomically)
{
    expect_face_rejected_without_destination_mutation(
        [](SourceKeyedFaceLimitRows &face) {
            face.samples[0].rows.pop_back();
        },
        LoopContractError::MissingDerivative);
    expect_face_rejected_without_destination_mutation(
        [](SourceKeyedFaceLimitRows &face) {
            SourceKeyedLimitRow &row = face.samples[0].rows[0];
            row.coefficients.push_back(row.coefficients[0]);
        },
        LoopContractError::DuplicateSource);
    expect_face_rejected_without_destination_mutation(
        [](SourceKeyedFaceLimitRows &face) {
            face.samples[0].rows[0].coefficients[0].coefficient =
                std::numeric_limits<double>::quiet_NaN();
        },
        LoopContractError::NonfiniteCoefficient);
    expect_face_rejected_without_destination_mutation(
        [](SourceKeyedFaceLimitRows &face) { face.faceId = 1; },
        LoopContractError::WrongFaceId);
    expect_face_rejected_without_destination_mutation(
        [](SourceKeyedFaceLimitRows &face) {
            face.samples[0].u = -0.1;
        },
        LoopContractError::InvalidSampleCoordinate);
    expect_face_rejected_without_destination_mutation(
        [](SourceKeyedFaceLimitRows &face) {
            face.samples[0].u = 0.8;
            face.samples[0].v = 0.4;
        },
        LoopContractError::InvalidSampleCoordinate);
    expect_face_rejected_without_destination_mutation(
        [](SourceKeyedFaceLimitRows &face) {
            face.samples[0].weight = 0.0;
        },
        LoopContractError::InvalidSampleWeight);
    expect_face_rejected_without_destination_mutation(
        [](SourceKeyedFaceLimitRows &face) {
            face.samples[0].weight =
                std::numeric_limits<double>::infinity();
        },
        LoopContractError::InvalidSampleWeight);
}

TEST(LoopLimitSurfaceContract,
     ScatterRejectsMalformedValuesWithoutPartialPublication)
{
    std::vector<double> destination(4, 1.25);
    const std::vector<double> unchanged = destination;
    EXPECT_EQ(scatter_by_original_source_ids(
                  {1, 1}, {2.0, 3.0}, destination)
                  .error,
              LoopContractError::DuplicateSource);
    EXPECT_EQ(destination, unchanged);
    EXPECT_EQ(scatter_by_original_source_ids(
                  {1, 3},
                  {2.0, std::numeric_limits<double>::infinity()},
                  destination)
                  .error,
              LoopContractError::NonfiniteScatterValue);
    EXPECT_EQ(destination, unchanged);
}

TEST(LoopLimitSurfaceContract,
     OneMixedDuvRowExpandsOnlyAtLegacyCompatibilitySeam)
{
    DenseLimitSampleRows sample;
    for (std::size_t row = 0; row < kLimitRowCount; ++row)
    {
        sample.rows[row] = {
            10.0 * static_cast<double>(row) + 1.0,
            10.0 * static_cast<double>(row) + 2.0};
    }

    std::array<std::vector<double>, kLegacyLimitRowCount> legacy;
    const LoopContractDiagnostic expanded =
        expand_mixed_row_for_legacy_compatibility(sample, legacy);
    ASSERT_TRUE(expanded.ok()) << expanded.message;
    EXPECT_EQ(legacy[4],
              sample.rows[limit_row_index(LimitRowKind::Dvv)]);
    EXPECT_EQ(legacy[5],
              sample.rows[limit_row_index(LimitRowKind::Duv)]);
    EXPECT_EQ(legacy[6],
              sample.rows[limit_row_index(LimitRowKind::Duv)]);
}

TEST(LoopLimitSurfaceContract,
     PackagePreparationRejectsIncompleteOrWrongFaceSets)
{
    std::vector<SourceKeyedFaceLimitRows> faces = make_valid_faces();
    faces[3].faceId = 4;
    PreparedLoopLimitRowsResult result = prepare_loop_limit_rows(
        make_valid_key(), 41, faces);
    EXPECT_FALSE(result.ok());
    EXPECT_EQ(result.diagnostic.error, LoopContractError::WrongFaceId);

    faces = make_valid_faces();
    faces.pop_back();
    result = prepare_loop_limit_rows(make_valid_key(), 41, faces);
    EXPECT_FALSE(result.ok());
    EXPECT_EQ(result.diagnostic.error,
              LoopContractError::CardinalityMismatch);

    LoopTopologyKey changed = make_valid_key();
    std::swap(changed.orientedTriangles[0][1],
              changed.orientedTriangles[0][2]);
    EXPECT_TRUE(topology_change_requires_invalidation(
        make_valid_key(), changed));
}
