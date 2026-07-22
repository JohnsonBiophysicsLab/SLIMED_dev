#include "mesh/Mesh.hpp"
#include "mesh/OpenSubdiv_regular_evaluator.hpp"

#include <opensubdiv/version.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <limits>
#include <memory>
#include <mutex>
#include <sstream>
#include <string>
#include <thread>
#include <utility>
#include <vector>

namespace
{
using RegularRowTable = std::vector<std::vector<Matrix>>;

class ScopedCoutSilencer
{
  public:
    ScopedCoutSilencer() : original_(std::cout.rdbuf(buffer_.rdbuf())) {}
    ~ScopedCoutSilencer() { std::cout.rdbuf(original_); }

  private:
    std::ostringstream buffer_;
    std::streambuf *original_;
};

class FingerprintBuilder
{
  public:
    void add_uint64(std::uint64_t value)
    {
        for (int shift = 0; shift < 64; shift += 8)
        {
            hash_ ^= static_cast<unsigned char>((value >> shift) & 0xffu);
            hash_ *= 1099511628211ull;
        }
    }

    void add_int(int value)
    {
        add_uint64(static_cast<std::uint64_t>(static_cast<std::int64_t>(value)));
    }
    void add_bool(bool value) { add_uint64(value ? 1u : 0u); }

    void add_double(double value)
    {
        std::uint64_t bits = 0;
        static_assert(sizeof(bits) == sizeof(value), "double fingerprint width");
        std::memcpy(&bits, &value, sizeof(bits));
        add_uint64(bits);
    }

    void add_string(const std::string &value)
    {
        add_uint64(value.size());
        for (unsigned char byte : value)
        {
            hash_ ^= byte;
            hash_ *= 1099511628211ull;
        }
    }

    void add_matrix(const Matrix &matrix)
    {
        add_int(matrix.nrow());
        add_int(matrix.ncol());
        for (int row = 0; row < matrix.nrow(); ++row)
        {
            for (int column = 0; column < matrix.ncol(); ++column)
            {
                add_double(matrix.get(row, column));
            }
        }
    }

    std::uint64_t value() const { return hash_; }

  private:
    std::uint64_t hash_ = 1469598103934665603ull;
};

std::uint64_t regular_cache_fingerprint(const Mesh &mesh)
{
    FingerprintBuilder fingerprint;
    fingerprint.add_string("slimed-opensubdiv-regular-cache-schema-v1");
    fingerprint.add_int(OPENSUBDIV_VERSION_NUMBER);
    fingerprint.add_string("loop");
    fingerprint.add_string("edge-and-corner-boundary");
    fingerprint.add_int(3);
    fingerprint.add_bool(true);
    fingerprint.add_bool(true);
    fingerprint.add_string("double-limit-stencils");
    fingerprint.add_double(5.0e-6);

    fingerprint.add_uint64(mesh.vertices.size());
    fingerprint.add_uint64(mesh.faces.size());
    for (const Face &face : mesh.faces)
    {
        fingerprint.add_int(face.index);
        fingerprint.add_bool(face.isBoundary);
        fingerprint.add_bool(face.isGhost);
        fingerprint.add_uint64(face.adjacentVertices.size());
        for (int source : face.adjacentVertices)
        {
            fingerprint.add_int(source);
        }
        fingerprint.add_uint64(face.oneRingVertices.size());
        for (int source : face.oneRingVertices)
        {
            fingerprint.add_int(source);
        }
    }

    fingerprint.add_matrix(mesh.param.VWU);
    fingerprint.add_matrix(mesh.param.gaussQuadratureCoeff);
    fingerprint.add_uint64(mesh.param.shapeFunctions.size());
    for (const Matrix &rows : mesh.param.shapeFunctions)
    {
        fingerprint.add_matrix(rows);
    }
    return fingerprint.value();
}

class PrototypeRegularRowCache
{
  public:
    PrototypeRegularRowCache() = default;
    PrototypeRegularRowCache(const PrototypeRegularRowCache &)
    {
        // Copied mesh-local caches start empty under the PR #107 contract.
    }

    PrototypeRegularRowCache &operator=(const PrototypeRegularRowCache &)
    {
        std::lock_guard<std::mutex> lock(mutex_);
        table_.reset();
        fingerprint_ = 0;
        buildCount_ = 0;
        hitCount_ = 0;
        missCount_ = 0;
        return *this;
    }

    PrototypeRegularRowCache(PrototypeRegularRowCache &&other) noexcept
    {
        std::lock_guard<std::mutex> lock(other.mutex_);
        transfer_from(other);
    }

    PrototypeRegularRowCache &operator=(PrototypeRegularRowCache &&other) noexcept
    {
        if (this == &other)
        {
            return *this;
        }
        std::scoped_lock lock(mutex_, other.mutex_);
        transfer_from(other);
        return *this;
    }

    std::shared_ptr<const RegularRowTable> get(const Mesh &mesh)
    {
        if (!opensubdiv_regular_production_routing_requested())
        {
            return {};
        }

        const std::uint64_t requestedFingerprint = regular_cache_fingerprint(mesh);
        std::lock_guard<std::mutex> lock(mutex_);
        if (table_ && fingerprint_ == requestedFingerprint)
        {
            ++hitCount_;
            return table_;
        }

        ++missCount_;
        table_ = std::make_shared<const RegularRowTable>(
            build_opensubdiv_regular_shape_functions_by_face(mesh));
        fingerprint_ = requestedFingerprint;
        ++buildCount_;
        return table_;
    }

    int build_count() const
    {
        std::lock_guard<std::mutex> lock(mutex_);
        return buildCount_;
    }
    int hit_count() const
    {
        std::lock_guard<std::mutex> lock(mutex_);
        return hitCount_;
    }
    int miss_count() const
    {
        std::lock_guard<std::mutex> lock(mutex_);
        return missCount_;
    }

  private:
    void transfer_from(PrototypeRegularRowCache &other)
    {
        table_ = std::move(other.table_);
        fingerprint_ = other.fingerprint_;
        buildCount_ = other.buildCount_;
        hitCount_ = other.hitCount_;
        missCount_ = other.missCount_;
        other.fingerprint_ = 0;
        other.buildCount_ = 0;
        other.hitCount_ = 0;
        other.missCount_ = 0;
    }

    mutable std::mutex mutex_;
    std::shared_ptr<const RegularRowTable> table_;
    std::uint64_t fingerprint_ = 0;
    int buildCount_ = 0;
    int hitCount_ = 0;
    int missCount_ = 0;
};

struct MeshFixture
{
    Param param;
    Mesh mesh;

    MeshFixture() : mesh(param)
    {
        param.VERBOSE_MODE = false;
        param.boundaryCondition = BoundaryType::Periodic;
        param.sideX = 40.0;
        param.sideY = 10.0 * std::sqrt(3.0) / 2.0 * param.lFace;
        ScopedCoutSilencer silence;
        mesh.setup_flat();
    }
};

double max_row_difference(const RegularRowTable &table,
                          const std::vector<Matrix> &reference)
{
    double maximum = 0.0;
    for (const std::vector<Matrix> &faceRows : table)
    {
        if (faceRows.empty())
        {
            continue;
        }
        if (faceRows.size() != reference.size())
        {
            return std::numeric_limits<double>::infinity();
        }
        for (std::size_t sample = 0; sample < faceRows.size(); ++sample)
        {
            if (faceRows[sample].nrow() != reference[sample].nrow() ||
                faceRows[sample].ncol() != reference[sample].ncol())
            {
                return std::numeric_limits<double>::infinity();
            }
            for (int row = 0; row < faceRows[sample].nrow(); ++row)
            {
                for (int column = 0; column < faceRows[sample].ncol(); ++column)
                {
                    maximum = std::max(
                        maximum,
                        std::abs(faceRows[sample].get(row, column) -
                                 reference[sample].get(row, column)));
                }
            }
        }
    }
    return maximum;
}

int populated_face_count(const RegularRowTable &table)
{
    return static_cast<int>(std::count_if(
        table.begin(), table.end(),
        [](const std::vector<Matrix> &rows) { return !rows.empty(); }));
}

bool unsupported_fallback_preserved(const Mesh &mesh,
                                    const RegularRowTable &table)
{
    bool foundUnsupported = false;
    for (const Face &face : mesh.faces)
    {
        const bool unsupported =
            face.isBoundary || face.isGhost || face.oneRingVertices.size() != 12u;
        if (!unsupported)
        {
            continue;
        }
        foundUnsupported = true;
        if (face.index < 0 ||
            face.index >= static_cast<int>(table.size()) ||
            !table[face.index].empty())
        {
            return false;
        }
    }
    return foundUnsupported;
}

struct ProofResult
{
    bool oneBuildForUnchanged = false;
    bool coordinateOnlyHit = false;
    bool topologyMutationMiss = false;
    bool samplePlanMutationMiss = false;
    bool copyStartsEmpty = false;
    bool moveTransfersMatchingTable = false;
    bool twoMeshIsolation = false;
    bool concurrentReadersOnePublisher = false;
    bool runtimeOptOutIgnoresPopulatedCache = false;
    bool unsupportedFallbackPreserved = false;
    bool rowsMatchFrozenRegular = false;
    int populatedFaceCount = 0;
    int buildCount = 0;
    int hitCount = 0;
    int missCount = 0;
    double maxRowDifference = 0.0;
};

ProofResult run_proof()
{
    setenv("SLIMED_USE_OPENSUBDIV_REGULAR", "1", 1);
    MeshFixture fixture;
    PrototypeRegularRowCache cache;
    const std::shared_ptr<const RegularRowTable> initial = cache.get(fixture.mesh);
    const std::shared_ptr<const RegularRowTable> unchanged = cache.get(fixture.mesh);

    ProofResult result;
    result.oneBuildForUnchanged =
        initial && initial == unchanged && cache.build_count() == 1;

    fixture.mesh.vertices.front().coord.set(
        2, 0, fixture.mesh.vertices.front().coord.get(2, 0) + 0.125);
    result.coordinateOnlyHit =
        cache.get(fixture.mesh) == initial && cache.build_count() == 1;

    const auto faceIterator = std::find_if(
        fixture.mesh.faces.begin(), fixture.mesh.faces.end(),
        [](const Face &face) {
            return !face.isBoundary && !face.isGhost &&
                   face.oneRingVertices.size() == 12u;
        });
    if (faceIterator == fixture.mesh.faces.end())
    {
        return result;
    }
    Face &mutableFace = *faceIterator;
    std::swap(mutableFace.oneRingVertices[0], mutableFace.oneRingVertices[1]);
    const std::shared_ptr<const RegularRowTable> topologyMutation =
        cache.get(fixture.mesh);
    result.topologyMutationMiss =
        topologyMutation && topologyMutation != initial && cache.build_count() == 2;
    std::swap(mutableFace.oneRingVertices[0], mutableFace.oneRingVertices[1]);
    cache.get(fixture.mesh);

    const double originalSample = fixture.param.VWU.get(0, 0);
    fixture.param.VWU.set(0, 0, originalSample + 0.01);
    const int buildsBeforeSampleMutation = cache.build_count();
    const std::shared_ptr<const RegularRowTable> sampleMutation =
        cache.get(fixture.mesh);
    result.samplePlanMutationMiss =
        sampleMutation && cache.build_count() == buildsBeforeSampleMutation + 1;
    fixture.param.VWU.set(0, 0, originalSample);
    cache.get(fixture.mesh);

    PrototypeRegularRowCache copied(cache);
    result.copyStartsEmpty = copied.build_count() == 0;
    const std::shared_ptr<const RegularRowTable> copiedTable = copied.get(fixture.mesh);
    result.copyStartsEmpty = result.copyStartsEmpty && copied.build_count() == 1 &&
                             copiedTable && copiedTable != cache.get(fixture.mesh);

    PrototypeRegularRowCache moved(std::move(copied));
    const int movedBuilds = moved.build_count();
    result.moveTransfersMatchingTable =
        moved.get(fixture.mesh) == copiedTable && moved.build_count() == movedBuilds;

    MeshFixture secondFixture;
    PrototypeRegularRowCache secondCache;
    const std::shared_ptr<const RegularRowTable> secondTable =
        secondCache.get(secondFixture.mesh);
    result.twoMeshIsolation = secondTable && secondTable != initial &&
                              secondCache.build_count() == 1;

    PrototypeRegularRowCache concurrentCache;
    std::vector<std::shared_ptr<const RegularRowTable>> concurrentTables(6);
    std::vector<std::thread> readers;
    for (std::size_t index = 0; index < concurrentTables.size(); ++index)
    {
        readers.emplace_back([&fixture, &concurrentCache, &concurrentTables, index]() {
            concurrentTables[index] = concurrentCache.get(fixture.mesh);
        });
    }
    for (std::thread &reader : readers)
    {
        reader.join();
    }
    result.concurrentReadersOnePublisher =
        concurrentCache.build_count() == 1 && concurrentTables.front() &&
        std::all_of(concurrentTables.begin(), concurrentTables.end(),
                    [&concurrentTables](const auto &table) {
                        return table == concurrentTables.front();
                    });

    unsetenv("SLIMED_USE_OPENSUBDIV_REGULAR");
    const int buildsBeforeOptOut = cache.build_count();
    result.runtimeOptOutIgnoresPopulatedCache =
        !cache.get(fixture.mesh) && cache.build_count() == buildsBeforeOptOut;
    setenv("SLIMED_USE_OPENSUBDIV_REGULAR", "1", 1);

    result.populatedFaceCount = initial ? populated_face_count(*initial) : 0;
    result.unsupportedFallbackPreserved =
        initial && result.populatedFaceCount > 0 &&
        unsupported_fallback_preserved(fixture.mesh, *initial);
    result.maxRowDifference =
        initial ? max_row_difference(*initial, fixture.param.shapeFunctions)
                : std::numeric_limits<double>::infinity();
    result.rowsMatchFrozenRegular =
        std::isfinite(result.maxRowDifference) && result.maxRowDifference <= 5.0e-6;
    result.buildCount = cache.build_count();
    result.hitCount = cache.hit_count();
    result.missCount = cache.miss_count();
    return result;
}

bool passed(const ProofResult &result)
{
    return result.oneBuildForUnchanged && result.coordinateOnlyHit &&
           result.topologyMutationMiss && result.samplePlanMutationMiss &&
           result.copyStartsEmpty && result.moveTransfersMatchingTable &&
           result.twoMeshIsolation && result.concurrentReadersOnePublisher &&
           result.runtimeOptOutIgnoresPopulatedCache &&
           result.unsupportedFallbackPreserved && result.rowsMatchFrozenRegular;
}

void print_bool(const char *name, bool value)
{
    std::cout << '"' << name << "\":" << (value ? "true" : "false") << ',';
}
} // namespace

int main()
{
    const ProofResult result = run_proof();
    const bool success = passed(result);
    std::cout << std::setprecision(17) << '{';
    std::cout << "\"kind\":\"test_only_opensubdiv_regular_cache_prototype\",";
    print_bool("not_production_cache", true);
    print_bool("not_production_routing_change", true);
    print_bool("passed", success);
    print_bool("one_build_for_unchanged", result.oneBuildForUnchanged);
    print_bool("coordinate_only_hit", result.coordinateOnlyHit);
    print_bool("topology_mutation_miss", result.topologyMutationMiss);
    print_bool("sample_plan_mutation_miss", result.samplePlanMutationMiss);
    print_bool("copy_starts_empty", result.copyStartsEmpty);
    print_bool("move_transfers_matching_table", result.moveTransfersMatchingTable);
    print_bool("two_mesh_isolation", result.twoMeshIsolation);
    print_bool("concurrent_readers_one_publisher", result.concurrentReadersOnePublisher);
    print_bool("runtime_opt_out_ignores_populated_cache",
               result.runtimeOptOutIgnoresPopulatedCache);
    print_bool("unsupported_fallback_preserved", result.unsupportedFallbackPreserved);
    print_bool("rows_match_frozen_regular", result.rowsMatchFrozenRegular);
    std::cout << "\"populated_face_count\":" << result.populatedFaceCount << ',';
    std::cout << "\"build_count\":" << result.buildCount << ',';
    std::cout << "\"hit_count\":" << result.hitCount << ',';
    std::cout << "\"miss_count\":" << result.missCount << ',';
    std::cout << "\"max_row_difference\":" << result.maxRowDifference;
    std::cout << "}\n";
    return success ? 0 : 1;
}
