/**
 * @file Loop_limit_surface_backend.hpp
 * @brief Immutable backend-neutral topology and prepared-row contracts.
 */

#pragma once

#include <algorithm>
#include <array>
#include <cstdint>
#include <limits>
#include <map>
#include <memory>
#include <set>
#include <string>
#include <utility>
#include <vector>

#include "mesh/Source_keyed_limit_rows.hpp"

namespace slimed::loop_limit
{

constexpr int kMinimumBfrApproximationLevel = 0;
constexpr int kMaximumBfrApproximationLevel = 255;

enum class BfrCacheMode
{
    Unset,
    Serial,
    Threaded
};

enum class LoopBoundaryPolicy
{
    Unset,
    Reject
};

enum class LoopGhostPolicy
{
    Unset,
    Reject
};

enum class LoopHolePolicy
{
    Unset,
    Reject
};

struct LoopTopologyPolicy
{
    LoopBoundaryPolicy boundary = LoopBoundaryPolicy::Unset;
    LoopGhostPolicy ghosts = LoopGhostPolicy::Unset;
    LoopHolePolicy holes = LoopHolePolicy::Unset;
};

inline bool operator==(const LoopTopologyPolicy &left,
                       const LoopTopologyPolicy &right) noexcept
{
    return left.boundary == right.boundary &&
           left.ghosts == right.ghosts &&
           left.holes == right.holes;
}

inline bool operator!=(const LoopTopologyPolicy &left,
                       const LoopTopologyPolicy &right) noexcept
{
    return !(left == right);
}

/**
 * Plain cache identity data. Coordinates are intentionally absent: only
 * topology- or row-affecting fields belong here.
 */
struct LoopTopologyKey
{
    std::uint64_t topologyEpoch = 0;
    std::string evaluatorApi;
    int bfrApproxLevelSmooth = -1;
    int bfrApproxLevelSharp = -1;
    BfrCacheMode bfrCacheMode = BfrCacheMode::Unset;
    int opensubdivVersion = 0;
    int sourceVertexCount = 0;
    std::vector<std::array<int, 3>> orientedTriangles;
    LoopTopologyPolicy topologyPolicy;
    std::string quadraturePolicy;
};

inline bool operator==(const LoopTopologyKey &left,
                       const LoopTopologyKey &right)
{
    return left.topologyEpoch == right.topologyEpoch &&
           left.evaluatorApi == right.evaluatorApi &&
           left.bfrApproxLevelSmooth == right.bfrApproxLevelSmooth &&
           left.bfrApproxLevelSharp == right.bfrApproxLevelSharp &&
           left.bfrCacheMode == right.bfrCacheMode &&
           left.opensubdivVersion == right.opensubdivVersion &&
           left.sourceVertexCount == right.sourceVertexCount &&
           left.orientedTriangles == right.orientedTriangles &&
           left.topologyPolicy == right.topologyPolicy &&
           left.quadraturePolicy == right.quadraturePolicy;
}

inline bool operator!=(const LoopTopologyKey &left,
                       const LoopTopologyKey &right)
{
    return !(left == right);
}

inline bool is_valid_bfr_cache_mode(BfrCacheMode mode) noexcept
{
    return mode == BfrCacheMode::Serial ||
           mode == BfrCacheMode::Threaded;
}

/**
 * Validate a production key as plain data. No library type, setter, cache, or
 * destination is consulted or changed by this function.
 */
inline LoopContractDiagnostic validate_production_loop_topology_key(
    const LoopTopologyKey &candidate)
{
    if (candidate.evaluatorApi != "bfr-surface")
    {
        return loop_contract_failure(
            LoopContractError::UnsupportedEvaluatorApi,
            "production Loop evaluator API must be exactly bfr-surface");
    }
    if (candidate.bfrApproxLevelSmooth <
            kMinimumBfrApproximationLevel ||
        candidate.bfrApproxLevelSmooth >
            kMaximumBfrApproximationLevel ||
        candidate.bfrApproxLevelSharp <
            kMinimumBfrApproximationLevel ||
        candidate.bfrApproxLevelSharp >
            kMaximumBfrApproximationLevel)
    {
        return loop_contract_failure(
            LoopContractError::ApproximationLevelOutOfRange,
            "Bfr approximation levels must be integers in [0, 255]");
    }
    if (!is_valid_bfr_cache_mode(candidate.bfrCacheMode))
    {
        return loop_contract_failure(
            LoopContractError::InvalidCacheMode,
            "Bfr cache mode must select serial or threaded caching");
    }
    if (candidate.opensubdivVersion <= 0)
    {
        return loop_contract_failure(
            LoopContractError::UnpopulatedVersion,
            "Loop topology key requires a populated positive version");
    }
    if (candidate.topologyEpoch == 0)
    {
        return loop_contract_failure(
            LoopContractError::UnpopulatedTopologyEpoch,
            "Loop topology epoch must be populated");
    }
    if (candidate.topologyPolicy.boundary != LoopBoundaryPolicy::Reject ||
        candidate.topologyPolicy.ghosts != LoopGhostPolicy::Reject ||
        candidate.topologyPolicy.holes != LoopHolePolicy::Reject)
    {
        return loop_contract_failure(
            LoopContractError::InvalidTopologyPolicy,
            "Loop proof policy must reject boundaries, ghosts, and holes");
    }
    if (candidate.quadraturePolicy.empty())
    {
        return loop_contract_failure(
            LoopContractError::InvalidQuadraturePolicy,
            "Loop topology key requires a fixed quadrature policy tag");
    }
    if (candidate.sourceVertexCount <= 0 ||
        candidate.orientedTriangles.empty())
    {
        return loop_contract_failure(
            LoopContractError::InvalidTopology,
            "Loop topology key requires sources and oriented triangles");
    }

    struct EdgeIncidence
    {
        int count = 0;
        int directedBalance = 0;
    };

    std::set<std::array<int, 3>> seenFaces;
    std::map<std::array<int, 2>, EdgeIncidence> edgeIncidences;
    std::vector<bool> referencedSources(
        static_cast<std::size_t>(candidate.sourceVertexCount), false);
    std::vector<std::map<int, std::set<int>>> vertexLinks(
        static_cast<std::size_t>(candidate.sourceVertexCount));
    for (std::size_t faceIndex = 0;
         faceIndex < candidate.orientedTriangles.size();
         ++faceIndex)
    {
        const std::array<int, 3> &face =
            candidate.orientedTriangles[faceIndex];
        if (face[0] < 0 || face[1] < 0 || face[2] < 0 ||
            face[0] >= candidate.sourceVertexCount ||
            face[1] >= candidate.sourceVertexCount ||
            face[2] >= candidate.sourceVertexCount ||
            face[0] == face[1] || face[1] == face[2] ||
            face[2] == face[0])
        {
            return loop_contract_failure(
                LoopContractError::InvalidTopology,
                "Loop topology contains an invalid oriented triangle",
                static_cast<int>(faceIndex));
        }
        std::array<int, 3> canonicalFace = face;
        std::sort(canonicalFace.begin(), canonicalFace.end());
        if (!seenFaces.insert(canonicalFace).second)
        {
            return loop_contract_failure(
                LoopContractError::DuplicateFace,
                "Loop topology contains a duplicate oriented triangle",
                static_cast<int>(faceIndex));
        }
        referencedSources[static_cast<std::size_t>(face[0])] = true;
        referencedSources[static_cast<std::size_t>(face[1])] = true;
        referencedSources[static_cast<std::size_t>(face[2])] = true;

        for (int corner = 0; corner < 3; ++corner)
        {
            const int source = face[static_cast<std::size_t>(corner)];
            const int firstNeighbor =
                face[static_cast<std::size_t>((corner + 1) % 3)];
            const int secondNeighbor =
                face[static_cast<std::size_t>((corner + 2) % 3)];
            vertexLinks[static_cast<std::size_t>(source)][firstNeighbor]
                .insert(secondNeighbor);
            vertexLinks[static_cast<std::size_t>(source)][secondNeighbor]
                .insert(firstNeighbor);
        }

        for (int edgeIndex = 0; edgeIndex < 3; ++edgeIndex)
        {
            const int from = face[static_cast<std::size_t>(edgeIndex)];
            const int to =
                face[static_cast<std::size_t>((edgeIndex + 1) % 3)];
            const std::array<int, 2> edge{{std::min(from, to),
                                            std::max(from, to)}};
            EdgeIncidence &incidence = edgeIncidences[edge];
            ++incidence.count;
            incidence.directedBalance += from < to ? 1 : -1;
        }
    }

    if (std::any_of(referencedSources.begin(),
                    referencedSources.end(),
                    [](bool referenced) { return !referenced; }))
    {
        return loop_contract_failure(
            LoopContractError::InvalidTopology,
            "Loop topology contains an unreferenced source vertex");
    }

    for (const auto &entry : edgeIncidences)
    {
        if (entry.second.count > 2)
        {
            return loop_contract_failure(
                LoopContractError::NonManifoldEdgeIncidence,
                "Loop topology contains an edge incident to more than two faces");
        }
    }
    for (const auto &entry : edgeIncidences)
    {
        if (entry.second.count != 2)
        {
            return loop_contract_failure(
                LoopContractError::BoundaryOrHoleEdge,
                "Loop topology contains a boundary or hole edge");
        }
    }
    for (const auto &entry : edgeIncidences)
    {
        if (entry.second.directedBalance != 0)
        {
            return loop_contract_failure(
                LoopContractError::InconsistentOrientation,
                "Loop topology edge incidences have inconsistent orientation");
        }
    }

    for (std::size_t source = 0; source < vertexLinks.size(); ++source)
    {
        const std::map<int, std::set<int>> &link = vertexLinks[source];
        if (link.empty() ||
            std::any_of(
                link.begin(),
                link.end(),
                [](const auto &entry) {
                    return entry.second.size() != 2;
                }))
        {
            return loop_contract_failure(
                LoopContractError::NonManifoldVertexIncidence,
                "Loop topology vertex link is not a closed cycle",
                -1,
                -1,
                static_cast<int>(source));
        }

        std::set<int> visited;
        std::vector<int> pending{link.begin()->first};
        while (!pending.empty())
        {
            const int neighbor = pending.back();
            pending.pop_back();
            if (!visited.insert(neighbor).second)
            {
                continue;
            }
            const auto adjacency = link.find(neighbor);
            if (adjacency == link.end())
            {
                return loop_contract_failure(
                    LoopContractError::NonManifoldVertexIncidence,
                    "Loop topology vertex link is not a closed cycle",
                    -1,
                    -1,
                    static_cast<int>(source));
            }
            pending.insert(pending.end(),
                           adjacency->second.begin(),
                           adjacency->second.end());
        }
        if (visited.size() != link.size())
        {
            return loop_contract_failure(
                LoopContractError::NonManifoldVertexIncidence,
                "Loop topology vertex link contains disconnected cycles",
                -1,
                -1,
                static_cast<int>(source));
        }
    }
    return loop_contract_ok();
}

/**
 * Publish a validated production key only after every field has passed.
 */
inline LoopContractDiagnostic assign_validated_production_loop_topology_key(
    const LoopTopologyKey &candidate,
    LoopTopologyKey &destination)
{
    const LoopContractDiagnostic validation =
        validate_production_loop_topology_key(candidate);
    if (!validation.ok())
    {
        return validation;
    }
    destination = candidate;
    return loop_contract_ok();
}

enum class LoopTopologyInvalidationReason
{
    Setup,
    Remeshing,
    AcceptedEdgeFlip,
    OrientationChange
};

inline bool is_valid_invalidation_reason(
    LoopTopologyInvalidationReason reason) noexcept
{
    return reason == LoopTopologyInvalidationReason::Setup ||
           reason == LoopTopologyInvalidationReason::Remeshing ||
           reason == LoopTopologyInvalidationReason::AcceptedEdgeFlip ||
           reason == LoopTopologyInvalidationReason::OrientationChange;
}

inline LoopContractDiagnostic validate_topology_epoch_transition(
    std::uint64_t currentEpoch,
    std::uint64_t proposedEpoch)
{
    if (currentEpoch == 0 || proposedEpoch <= currentEpoch)
    {
        return loop_contract_failure(
            LoopContractError::InvalidTopologyEpochTransition,
            "Loop topology epoch must increase monotonically");
    }
    return loop_contract_ok();
}

/**
 * Hook used by all named topology mutations to advance exactly one epoch.
 * The destination remains unchanged on invalid reason or overflow.
 */
inline LoopContractDiagnostic assign_next_topology_epoch(
    std::uint64_t currentEpoch,
    LoopTopologyInvalidationReason reason,
    std::uint64_t &destination)
{
    if (currentEpoch == 0 ||
        currentEpoch == std::numeric_limits<std::uint64_t>::max() ||
        !is_valid_invalidation_reason(reason))
    {
        return loop_contract_failure(
            LoopContractError::InvalidTopologyEpochTransition,
            "Loop topology invalidation cannot advance this epoch");
    }
    destination = currentEpoch + 1;
    return loop_contract_ok();
}

struct PreparedFaceLimitRows
{
    SourceKeyedFaceLimitRows sparseRows;
    std::vector<int> unionSourceIds;
};

class PreparedLoopLimitRows;

struct PreparedLoopLimitRowsResult
{
    std::shared_ptr<const PreparedLoopLimitRows> package;
    LoopContractDiagnostic diagnostic;

    bool ok() const noexcept
    {
        return package != nullptr && diagnostic.ok();
    }
};

PreparedLoopLimitRowsResult prepare_loop_limit_rows(
    const LoopTopologyKey &key,
    std::uint64_t activeTopologyEpoch,
    const std::vector<SourceKeyedFaceLimitRows> &faces);

class PreparedLoopLimitRows
{
public:
    const LoopTopologyKey &topology_key() const noexcept
    {
        return key_;
    }

    const std::vector<PreparedFaceLimitRows> &faces() const noexcept
    {
        return faces_;
    }

    const PreparedFaceLimitRows *find_face(int faceId) const noexcept
    {
        if (faceId < 0 ||
            faceId >= static_cast<int>(faces_.size()) ||
            faces_[static_cast<std::size_t>(faceId)].sparseRows.faceId !=
                faceId)
        {
            return nullptr;
        }
        return &faces_[static_cast<std::size_t>(faceId)];
    }

private:
    PreparedLoopLimitRows(LoopTopologyKey key,
                          std::vector<PreparedFaceLimitRows> faces)
        : key_(std::move(key)), faces_(std::move(faces))
    {
    }

    LoopTopologyKey key_;
    std::vector<PreparedFaceLimitRows> faces_;

    friend PreparedLoopLimitRowsResult prepare_loop_limit_rows(
        const LoopTopologyKey &key,
        std::uint64_t activeTopologyEpoch,
        const std::vector<SourceKeyedFaceLimitRows> &faces);
};

inline PreparedLoopLimitRowsResult prepare_loop_limit_rows(
    const LoopTopologyKey &key,
    std::uint64_t activeTopologyEpoch,
    const std::vector<SourceKeyedFaceLimitRows> &faces)
{
    const LoopContractDiagnostic keyValidation =
        validate_production_loop_topology_key(key);
    if (!keyValidation.ok())
    {
        return {nullptr, keyValidation};
    }
    if (key.topologyEpoch != activeTopologyEpoch)
    {
        return {
            nullptr,
            loop_contract_failure(
                LoopContractError::StaleTopologyEpoch,
                "Loop row preparation rejected a stale topology epoch")};
    }
    if (faces.size() != key.orientedTriangles.size())
    {
        return {
            nullptr,
            loop_contract_failure(
                LoopContractError::CardinalityMismatch,
                "Loop row package must contain every topology face")};
    }

    std::vector<PreparedFaceLimitRows> stagedFaces;
    stagedFaces.reserve(faces.size());
    std::set<int> seenFaceIds;
    for (const SourceKeyedFaceLimitRows &face : faces)
    {
        if (face.faceId < 0 ||
            face.faceId >= static_cast<int>(key.orientedTriangles.size()))
        {
            return {
                nullptr,
                loop_contract_failure(
                    LoopContractError::WrongFaceId,
                    "Loop row package contains a face outside the topology",
                    face.faceId)};
        }
        if (!seenFaceIds.insert(face.faceId).second)
        {
            return {
                nullptr,
                loop_contract_failure(
                    LoopContractError::DuplicateFace,
                    "Loop row package contains a duplicate face ID",
                    face.faceId)};
        }

        PreparedFaceLimitRows preparedFace;
        const LoopContractDiagnostic faceValidation =
            canonicalize_source_keyed_face(
                face,
                face.faceId,
                key.sourceVertexCount,
                preparedFace.sparseRows,
                preparedFace.unionSourceIds);
        if (!faceValidation.ok())
        {
            return {nullptr, faceValidation};
        }
        stagedFaces.push_back(std::move(preparedFace));
    }
    std::sort(stagedFaces.begin(),
              stagedFaces.end(),
              [](const PreparedFaceLimitRows &left,
                 const PreparedFaceLimitRows &right) {
                  return left.sparseRows.faceId < right.sparseRows.faceId;
              });

    const std::shared_ptr<const PreparedLoopLimitRows> package(
        new PreparedLoopLimitRows(key, std::move(stagedFaces)));
    return {package, loop_contract_ok()};
}

inline bool prepared_package_cache_identity_matches(
    const PreparedLoopLimitRows &package,
    const LoopTopologyKey &requestKey)
{
    return package.topology_key() == requestKey;
}

struct PreparedLoopLimitRowsLookup
{
    std::shared_ptr<const PreparedLoopLimitRows> package;
    LoopContractDiagnostic diagnostic;

    bool hit() const noexcept
    {
        return package != nullptr && diagnostic.ok();
    }
};

/**
 * Return a package only for its exact immutable identity and active epoch.
 */
inline PreparedLoopLimitRowsLookup lookup_prepared_loop_limit_rows(
    const std::shared_ptr<const PreparedLoopLimitRows> &package,
    const LoopTopologyKey &requestKey,
    std::uint64_t activeTopologyEpoch)
{
    if (!package)
    {
        return {
            nullptr,
            loop_contract_failure(
                LoopContractError::MissingPreparedPackage,
                "Loop prepared-package cache is empty")};
    }
    if (activeTopologyEpoch == 0 ||
        package->topology_key().topologyEpoch != activeTopologyEpoch ||
        requestKey.topologyEpoch != activeTopologyEpoch)
    {
        return {
            nullptr,
            loop_contract_failure(
                LoopContractError::StaleTopologyEpoch,
                "Loop prepared package is stale for the active epoch")};
    }
    if (!prepared_package_cache_identity_matches(*package, requestKey))
    {
        return {
            nullptr,
            loop_contract_failure(
                LoopContractError::CacheIdentityMismatch,
                "Loop prepared package key does not match the request")};
    }
    return {package, loop_contract_ok()};
}

inline bool topology_change_requires_invalidation(
    const LoopTopologyKey &currentKey,
    const LoopTopologyKey &candidateKey)
{
    return currentKey != candidateKey;
}

} // namespace slimed::loop_limit
