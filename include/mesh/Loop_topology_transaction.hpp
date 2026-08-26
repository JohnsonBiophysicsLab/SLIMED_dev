#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

#include "mesh/Loop_topology_ownership.hpp"

class Mesh;

namespace slimed::loop_topology
{

enum class LoopTopologyTransactionState
{
    open,
    staged,
    rejected,
    committed,
    rolled_back
};

enum class LoopTopologyTransactionReason
{
    none,
    already_staged,
    not_staged,
    already_finalized,
    face_count_changed,
    topology_unchanged,
    topology_rejected,
    derived_rebuild_failed,
    source_generation_changed,
    source_cardinality_changed,
    source_connectivity_changed,
    generation_overflow,
    invalidation_failed
};

const char* loop_topology_transaction_reason_name(
    LoopTopologyTransactionReason reason);

struct LoopTopologyTransactionResult
{
    LoopTopologyTransactionReason reason =
        LoopTopologyTransactionReason::none;
    LoopTopologyReasonCode topology_reason = LoopTopologyReasonCode::none;

    bool accepted() const noexcept
    {
        return reason == LoopTopologyTransactionReason::none;
    }
};

/**
 * Stage and atomically install one fixed-cardinality face-connectivity edit.
 *
 * The caller must hold exclusive access to the Mesh for the lifetime of the
 * transaction. Staging and rejection never write live Mesh state. A successful
 * commit invalidates topology-derived cache state, advances the Mesh topology
 * generation once, and then installs only prebuilt vectors through noexcept
 * swaps. The transaction does not make the resulting topology evaluator-ready:
 * evaluator-specific one-rings are cleared for a later Gate-C rebuild.
 */
class LoopTopologyTransaction
{
public:
    explicit LoopTopologyTransaction(Mesh& mesh);

    LoopTopologyTransaction(const LoopTopologyTransaction&) = delete;
    LoopTopologyTransaction& operator=(const LoopTopologyTransaction&) = delete;
    LoopTopologyTransaction(LoopTopologyTransaction&&) = delete;
    LoopTopologyTransaction& operator=(LoopTopologyTransaction&&) = delete;

    LoopTopologyTransactionResult stage(
        const std::vector<std::vector<int>>& candidate_face_vertices);
    LoopTopologyTransactionResult commit() noexcept;
    LoopTopologyTransactionResult rollback() noexcept;

    LoopTopologyTransactionState state() const noexcept
    {
        return state_;
    }

    const LoopTopologyBuildResult& validation_result() const noexcept
    {
        return validation_;
    }

private:
    Mesh& mesh_;
    std::uint64_t source_generation_ = 0;
    std::size_t source_vertex_count_ = 0;
    std::size_t source_face_count_ = 0;
    std::vector<std::vector<int>> source_face_vertices_;
    LoopTopologyTransactionState state_ = LoopTopologyTransactionState::open;
    LoopTopologyBuildResult validation_;

    std::vector<std::vector<int>> staged_face_vertices_;
    std::vector<std::vector<int>> staged_face_neighbors_;
    std::vector<std::vector<int>> staged_face_one_rings_;
    std::vector<std::vector<int>> staged_vertex_faces_;
    std::vector<std::vector<int>> staged_vertex_neighbors_;
};

} // namespace slimed::loop_topology
