/**
 * @file Source_keyed_limit_rows.hpp
 * @brief Backend-neutral sparse Loop limit-row and dense-algebra contracts.
 */

#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <iterator>
#include <set>
#include <string>
#include <utility>
#include <vector>

namespace slimed::loop_limit
{

enum class LoopContractError
{
    None,
    UnsupportedEvaluatorApi,
    ApproximationLevelOutOfRange,
    InvalidCacheMode,
    UnpopulatedVersion,
    UnpopulatedTopologyEpoch,
    InvalidTopologyEpochTransition,
    InvalidTopologyPolicy,
    InvalidTopology,
    BoundaryOrHoleEdge,
    NonManifoldEdgeIncidence,
    NonManifoldVertexIncidence,
    InconsistentOrientation,
    InvalidQuadraturePolicy,
    StaleTopologyEpoch,
    CacheIdentityMismatch,
    MissingPreparedPackage,
    WrongFaceId,
    DuplicateFace,
    MissingDerivative,
    DuplicateDerivative,
    EmptyRow,
    DuplicateSource,
    SourceOutOfRange,
    NonfiniteCoefficient,
    InvalidSampleCoordinate,
    InvalidSampleWeight,
    CardinalityMismatch,
    NonfiniteScatterValue
};

struct LoopContractDiagnostic
{
    LoopContractError error = LoopContractError::None;
    int faceId = -1;
    int sampleIndex = -1;
    int sourceId = -1;
    std::string message;

    bool ok() const noexcept
    {
        return error == LoopContractError::None;
    }
};

inline LoopContractDiagnostic loop_contract_ok()
{
    return {};
}

inline LoopContractDiagnostic loop_contract_failure(
    LoopContractError error,
    std::string message,
    int faceId = -1,
    int sampleIndex = -1,
    int sourceId = -1)
{
    LoopContractDiagnostic diagnostic;
    diagnostic.error = error;
    diagnostic.faceId = faceId;
    diagnostic.sampleIndex = sampleIndex;
    diagnostic.sourceId = sourceId;
    diagnostic.message = std::move(message);
    return diagnostic;
}

enum class LimitRowKind
{
    Position = 0,
    Du = 1,
    Dv = 2,
    Duu = 3,
    Duv = 4,
    Dvv = 5
};

constexpr std::size_t kLimitRowCount = 6;
constexpr std::size_t kLegacyLimitRowCount = 7;

inline int limit_row_index(LimitRowKind kind) noexcept
{
    return static_cast<int>(kind);
}

inline bool is_valid_limit_row_kind(LimitRowKind kind) noexcept
{
    const int index = limit_row_index(kind);
    return index >= 0 && index < static_cast<int>(kLimitRowCount);
}

struct SourceCoefficient
{
    int sourceId = -1;
    double coefficient = 0.0;
};

struct SourceKeyedLimitRow
{
    LimitRowKind kind = LimitRowKind::Position;
    std::vector<SourceCoefficient> coefficients;
};

struct SourceKeyedLimitSample
{
    double u = 0.0;
    double v = 0.0;
    double weight = 0.0;
    std::vector<SourceKeyedLimitRow> rows;
};

struct SourceKeyedFaceLimitRows
{
    int faceId = -1;
    std::vector<SourceKeyedLimitSample> samples;
};

struct DenseLimitSampleRows
{
    double u = 0.0;
    double v = 0.0;
    double weight = 0.0;
    std::array<std::vector<double>, kLimitRowCount> rows;
};

struct DenseFaceLimitRows
{
    int faceId = -1;
    std::vector<int> unionSourceIds;
    std::vector<DenseLimitSampleRows> samples;
};

namespace detail
{

inline LoopContractDiagnostic canonicalize_source_keyed_face_impl(
    const SourceKeyedFaceLimitRows &input,
    int expectedFaceId,
    int sourceVertexCount,
    SourceKeyedFaceLimitRows &canonical,
    std::vector<int> &unionSourceIds)
{
    if (input.faceId != expectedFaceId)
    {
        return loop_contract_failure(
            LoopContractError::WrongFaceId,
            "source-keyed Loop rows do not match the requested face ID",
            input.faceId);
    }
    if (sourceVertexCount <= 0)
    {
        return loop_contract_failure(
            LoopContractError::InvalidTopology,
            "source-keyed Loop rows require a positive source vertex count",
            input.faceId);
    }
    if (input.samples.empty())
    {
        return loop_contract_failure(
            LoopContractError::CardinalityMismatch,
            "source-keyed Loop face contains no samples",
            input.faceId);
    }

    SourceKeyedFaceLimitRows staged;
    staged.faceId = input.faceId;
    staged.samples.reserve(input.samples.size());
    std::set<int> unionSources;

    for (std::size_t sampleIndex = 0;
         sampleIndex < input.samples.size();
         ++sampleIndex)
    {
        const SourceKeyedLimitSample &sample = input.samples[sampleIndex];
        if (!std::isfinite(sample.u) || !std::isfinite(sample.v) ||
            sample.u < 0.0 || sample.v < 0.0 ||
            sample.u + sample.v > 1.0)
        {
            return loop_contract_failure(
                LoopContractError::InvalidSampleCoordinate,
                "Loop sample coordinates must be finite triangle coordinates",
                input.faceId,
                static_cast<int>(sampleIndex));
        }
        if (!std::isfinite(sample.weight) || sample.weight <= 0.0)
        {
            return loop_contract_failure(
                LoopContractError::InvalidSampleWeight,
                "Loop sample weight must be finite and positive",
                input.faceId,
                static_cast<int>(sampleIndex));
        }

        std::array<bool, kLimitRowCount> seenRows{};
        std::array<SourceKeyedLimitRow, kLimitRowCount> orderedRows;
        for (const SourceKeyedLimitRow &row : sample.rows)
        {
            if (!is_valid_limit_row_kind(row.kind))
            {
                return loop_contract_failure(
                    LoopContractError::MissingDerivative,
                    "Loop sample contains an unknown derivative row",
                    input.faceId,
                    static_cast<int>(sampleIndex));
            }
            const int rowIndex = limit_row_index(row.kind);
            if (seenRows[static_cast<std::size_t>(rowIndex)])
            {
                return loop_contract_failure(
                    LoopContractError::DuplicateDerivative,
                    "Loop sample contains a duplicate derivative row",
                    input.faceId,
                    static_cast<int>(sampleIndex));
            }
            if (row.coefficients.empty())
            {
                return loop_contract_failure(
                    LoopContractError::EmptyRow,
                    "Loop derivative row contains no source coefficients",
                    input.faceId,
                    static_cast<int>(sampleIndex));
            }

            SourceKeyedLimitRow canonicalRow = row;
            std::sort(canonicalRow.coefficients.begin(),
                      canonicalRow.coefficients.end(),
                      [](const SourceCoefficient &left,
                         const SourceCoefficient &right) {
                          return left.sourceId < right.sourceId;
                      });
            int priorSourceId = -1;
            bool havePriorSource = false;
            for (const SourceCoefficient &entry : canonicalRow.coefficients)
            {
                if (entry.sourceId < 0 ||
                    entry.sourceId >= sourceVertexCount)
                {
                    return loop_contract_failure(
                        LoopContractError::SourceOutOfRange,
                        "Loop row source ID is outside the original mesh",
                        input.faceId,
                        static_cast<int>(sampleIndex),
                        entry.sourceId);
                }
                if (havePriorSource && entry.sourceId == priorSourceId)
                {
                    return loop_contract_failure(
                        LoopContractError::DuplicateSource,
                        "Loop derivative row contains a duplicate source ID",
                        input.faceId,
                        static_cast<int>(sampleIndex),
                        entry.sourceId);
                }
                if (!std::isfinite(entry.coefficient))
                {
                    return loop_contract_failure(
                        LoopContractError::NonfiniteCoefficient,
                        "Loop derivative row contains a nonfinite coefficient",
                        input.faceId,
                        static_cast<int>(sampleIndex),
                        entry.sourceId);
                }
                unionSources.insert(entry.sourceId);
                priorSourceId = entry.sourceId;
                havePriorSource = true;
            }
            seenRows[static_cast<std::size_t>(rowIndex)] = true;
            orderedRows[static_cast<std::size_t>(rowIndex)] =
                std::move(canonicalRow);
        }

        for (std::size_t rowIndex = 0;
             rowIndex < kLimitRowCount;
             ++rowIndex)
        {
            if (!seenRows[rowIndex])
            {
                return loop_contract_failure(
                    LoopContractError::MissingDerivative,
                    "Loop sample is missing a required derivative row",
                    input.faceId,
                    static_cast<int>(sampleIndex));
            }
        }

        SourceKeyedLimitSample canonicalSample;
        canonicalSample.u = sample.u;
        canonicalSample.v = sample.v;
        canonicalSample.weight = sample.weight;
        canonicalSample.rows.assign(
            std::make_move_iterator(orderedRows.begin()),
            std::make_move_iterator(orderedRows.end()));
        staged.samples.push_back(std::move(canonicalSample));
    }

    if (unionSources.empty())
    {
        return loop_contract_failure(
            LoopContractError::EmptyRow,
            "Loop face has no original sources",
            input.faceId);
    }

    std::vector<int> stagedUnion(unionSources.begin(), unionSources.end());
    canonical = std::move(staged);
    unionSourceIds = std::move(stagedUnion);
    return loop_contract_ok();
}

} // namespace detail

/**
 * Validate and canonicalize sparse rows without changing either destination
 * until every sample and row has passed validation.
 */
inline LoopContractDiagnostic canonicalize_source_keyed_face(
    const SourceKeyedFaceLimitRows &input,
    int expectedFaceId,
    int sourceVertexCount,
    SourceKeyedFaceLimitRows &canonical,
    std::vector<int> &unionSourceIds)
{
    return detail::canonicalize_source_keyed_face_impl(
        input,
        expectedFaceId,
        sourceVertexCount,
        canonical,
        unionSourceIds);
}

/**
 * Densify all six requested rows against one sorted per-face source union.
 */
inline LoopContractDiagnostic densify_source_keyed_face(
    const SourceKeyedFaceLimitRows &input,
    int expectedFaceId,
    int sourceVertexCount,
    DenseFaceLimitRows &destination)
{
    SourceKeyedFaceLimitRows canonical;
    std::vector<int> unionSourceIds;
    const LoopContractDiagnostic validation =
        detail::canonicalize_source_keyed_face_impl(
            input,
            expectedFaceId,
            sourceVertexCount,
            canonical,
            unionSourceIds);
    if (!validation.ok())
    {
        return validation;
    }

    DenseFaceLimitRows staged;
    staged.faceId = canonical.faceId;
    staged.unionSourceIds = unionSourceIds;
    staged.samples.reserve(canonical.samples.size());
    for (const SourceKeyedLimitSample &sample : canonical.samples)
    {
        DenseLimitSampleRows denseSample;
        denseSample.u = sample.u;
        denseSample.v = sample.v;
        denseSample.weight = sample.weight;
        for (std::size_t rowIndex = 0;
             rowIndex < kLimitRowCount;
             ++rowIndex)
        {
            denseSample.rows[rowIndex].assign(unionSourceIds.size(), 0.0);
            for (const SourceCoefficient &entry :
                 sample.rows[rowIndex].coefficients)
            {
                const auto source = std::lower_bound(
                    unionSourceIds.begin(),
                    unionSourceIds.end(),
                    entry.sourceId);
                const std::size_t denseIndex = static_cast<std::size_t>(
                    std::distance(unionSourceIds.begin(), source));
                denseSample.rows[rowIndex][denseIndex] = entry.coefficient;
            }
        }
        staged.samples.push_back(std::move(denseSample));
    }

    destination = std::move(staged);
    return loop_contract_ok();
}

/**
 * Expand the one stored mixed row only at the legacy seven-row seam.
 * Legacy row order is position, du, dv, duu, dvv, duv, duv.
 */
inline LoopContractDiagnostic expand_mixed_row_for_legacy_compatibility(
    const DenseLimitSampleRows &sample,
    std::array<std::vector<double>, kLegacyLimitRowCount> &destination)
{
    const std::size_t sourceCount = sample.rows[0].size();
    for (const std::vector<double> &row : sample.rows)
    {
        if (row.size() != sourceCount)
        {
            return loop_contract_failure(
                LoopContractError::CardinalityMismatch,
                "dense Loop rows do not share one source cardinality");
        }
        if (std::any_of(row.begin(), row.end(), [](double value) {
                return !std::isfinite(value);
            }))
        {
            return loop_contract_failure(
                LoopContractError::NonfiniteCoefficient,
                "dense Loop rows contain a nonfinite coefficient");
        }
    }

    std::array<std::vector<double>, kLegacyLimitRowCount> staged;
    staged[0] = sample.rows[limit_row_index(LimitRowKind::Position)];
    staged[1] = sample.rows[limit_row_index(LimitRowKind::Du)];
    staged[2] = sample.rows[limit_row_index(LimitRowKind::Dv)];
    staged[3] = sample.rows[limit_row_index(LimitRowKind::Duu)];
    staged[4] = sample.rows[limit_row_index(LimitRowKind::Dvv)];
    staged[5] = sample.rows[limit_row_index(LimitRowKind::Duv)];
    staged[6] = sample.rows[limit_row_index(LimitRowKind::Duv)];
    destination = std::move(staged);
    return loop_contract_ok();
}

/**
 * Scatter dense face-algebra values through the same original source IDs.
 * The destination is published only after the complete staged result is
 * finite and all IDs are valid and unique.
 */
inline LoopContractDiagnostic scatter_by_original_source_ids(
    const std::vector<int> &unionSourceIds,
    const std::vector<double> &sourceValues,
    std::vector<double> &destination)
{
    if (unionSourceIds.size() != sourceValues.size())
    {
        return loop_contract_failure(
            LoopContractError::CardinalityMismatch,
            "Loop scatter source IDs and values have different cardinality");
    }

    std::set<int> seenSources;
    for (std::size_t index = 0; index < unionSourceIds.size(); ++index)
    {
        const int sourceId = unionSourceIds[index];
        if (sourceId < 0 ||
            sourceId >= static_cast<int>(destination.size()))
        {
            return loop_contract_failure(
                LoopContractError::SourceOutOfRange,
                "Loop scatter source ID is outside the destination",
                -1,
                -1,
                sourceId);
        }
        if (!seenSources.insert(sourceId).second)
        {
            return loop_contract_failure(
                LoopContractError::DuplicateSource,
                "Loop scatter contains a duplicate source ID",
                -1,
                -1,
                sourceId);
        }
        if (!std::isfinite(sourceValues[index]))
        {
            return loop_contract_failure(
                LoopContractError::NonfiniteScatterValue,
                "Loop scatter contains a nonfinite source value",
                -1,
                -1,
                sourceId);
        }
    }

    std::vector<double> staged = destination;
    for (std::size_t index = 0; index < unionSourceIds.size(); ++index)
    {
        const int sourceId = unionSourceIds[index];
        staged[static_cast<std::size_t>(sourceId)] += sourceValues[index];
        if (!std::isfinite(staged[static_cast<std::size_t>(sourceId)]))
        {
            return loop_contract_failure(
                LoopContractError::NonfiniteScatterValue,
                "Loop scatter produced a nonfinite destination value",
                -1,
                -1,
                sourceId);
        }
    }
    destination = std::move(staged);
    return loop_contract_ok();
}

} // namespace slimed::loop_limit
