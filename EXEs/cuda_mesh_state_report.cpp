#include "cuda/Cuda_mesh_state.hpp"
#include "cuda/detail/Cuda_regular_geometry_cpu.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <string>
#include <vector>

namespace
{
using namespace slimed::cuda_residency;

constexpr double kTolerance = 1.0e-12;

struct GeometryFixture
{
    std::string name;
    RegularMeshPack pack;
    std::vector<double> candidate;
};

struct CaseResult
{
    std::string name;
    bool created = false;
    bool transitions = true;
    bool cpuParity = false;
    bool repeatable = true;
    bool ghostZero = true;
    bool degenerateZero = true;
    bool permutationEqual = true;
    double maxAbsError = 0.0;
    std::vector<double> firstAreas;
    std::vector<double> firstVolumes;
    double firstTotalArea = 0.0;
    double firstTotalVolume = 0.0;
    std::uint64_t commits = 0;
    std::uint64_t rollbacks = 0;
    std::uint64_t warmedAllocations = 0;
    DeviceStateReport activeReport;
    DeviceStateReport finalReport;
    DeviceStateError createError;

    bool pass() const
    {
        return created && transitions && cpuParity && repeatable && ghostZero &&
               degenerateZero && permutationEqual &&
               activeReport.phase == TransactionPhase::IdleAccepted &&
               finalReport.phase == TransactionPhase::Closed &&
               !finalReport.cleanupPending && finalReport.cleanupError.ok() &&
               finalReport.residentBytes == 0 &&
               finalReport.successfulAllocations == finalReport.successfulFrees;
    }
};

RegularMeshPack make_pack()
{
    RegularMeshPack pack;
    pack.generations = {1, 1, 1, 1, 1};
    pack.vertexCount = 12;
    pack.faceCount = 1;
    pack.evaluatedFaceCount = 1;
    pack.vertexBoundaryMask.assign(12, 0);
    pack.vertexGhostMask.assign(12, 0);
    pack.faceBoundaryMask = {0};
    pack.faceGhostMask = {0};
    pack.evaluatedFaceIds = {0};
    pack.orientedFaceVertexIds = {0, 1, 2};
    for (std::int32_t source = 0; source < 12; ++source)
        pack.oneRingSourceIds.push_back(source);
    pack.evaluatedFaceInsertionMask = {0};
    pack.evaluatedFaceSpontaneousCurvature = {0.0};
    for (std::uint64_t offset = 0; offset <= 12; ++offset)
        pack.sourceOffsets.push_back(offset);
    for (std::uint64_t occurrence = 0; occurrence < 12; ++occurrence)
        pack.sourceOccurrences.push_back(occurrence);
    pack.quadratureSamples.assign(9, 1.0 / 3.0);
    pack.quadratureCoefficients.assign(3, 1.0 / 3.0);
    pack.shapeWeights.assign(252, 0.0);
    pack.acceptedCoordinates.assign(36, 0.0);
    pack.previousCoordinates.assign(36, 0.0);
    pack.referenceCoordinates.assign(36, 0.0);
    const double controls[3][3]{{2.0, 0.0, 0.0},
                                {2.0, 1.0, 0.0},
                                {2.0, 0.0, 1.0}};
    for (std::size_t source = 0; source < 3; ++source)
        for (std::size_t axis = 0; axis < 3; ++axis)
            pack.acceptedCoordinates[source * 3 + axis] =
                pack.previousCoordinates[source * 3 + axis] =
                    pack.referenceCoordinates[source * 3 + axis] =
                        controls[source][axis];
    for (std::size_t sample = 0; sample < 3; ++sample)
    {
        const std::size_t base = sample * 7 * 12;
        pack.shapeWeights[base] = 1.0;
        pack.shapeWeights[base + 12] = -1.0;
        pack.shapeWeights[base + 13] = 1.0;
        pack.shapeWeights[base + 24] = -1.0;
        pack.shapeWeights[base + 26] = 1.0;
    }
    pack.parameters.kCurv = 1.0;
    return pack;
}

std::vector<GeometryFixture> make_fixtures()
{
    std::vector<GeometryFixture> fixtures;

    RegularMeshPack natural = make_pack();
    fixtures.push_back({"natural", natural, natural.acceptedCoordinates});

    RegularMeshPack permuted = make_pack();
    std::swap(permuted.oneRingSourceIds[1], permuted.oneRingSourceIds[2]);
    std::swap(permuted.sourceOccurrences[1], permuted.sourceOccurrences[2]);
    for (std::size_t sample = 0; sample < 3; ++sample)
        for (std::size_t row = 0; row < 7; ++row)
            std::swap(permuted.shapeWeights[(sample * 7 + row) * 12 + 1],
                      permuted.shapeWeights[(sample * 7 + row) * 12 + 2]);
    fixtures.push_back(
        {"permuted", permuted, permuted.acceptedCoordinates});

    RegularMeshPack curved = make_pack();
    const std::size_t sampleOne = 7 * 12;
    curved.shapeWeights[sampleOne + 12] = -2.0;
    curved.shapeWeights[sampleOne + 13] = 2.0;
    const std::size_t sampleTwo = 2 * 7 * 12;
    curved.shapeWeights[sampleTwo + 24] = -3.0;
    curved.shapeWeights[sampleTwo + 26] = 3.0;
    fixtures.push_back({"curved", curved, curved.acceptedCoordinates});

    RegularMeshPack boundaryGhost = make_pack();
    boundaryGhost.faceCount = 2;
    boundaryGhost.faceBoundaryMask = {1, 0};
    boundaryGhost.faceGhostMask = {0, 1};
    fixtures.push_back({"boundary_ghost", boundaryGhost,
                        boundaryGhost.acceptedCoordinates});

    RegularMeshPack degenerate = make_pack();
    std::vector<double> degenerateCoordinates(36, 2.0);
    fixtures.push_back(
        {"degenerate", degenerate, std::move(degenerateCoordinates)});

    RegularMeshPack production = make_pack();
    for (std::size_t source = 0; source < 12; ++source)
    {
        const double index = static_cast<double>(source);
        production.acceptedCoordinates[source * 3] =
            -1.2 + 0.37 * index + 0.02 * index * index;
        production.acceptedCoordinates[source * 3 + 1] =
            0.8 + 0.11 * index * index - 0.003 * index * index * index;
        production.acceptedCoordinates[source * 3 + 2] =
            0.15 * std::sin(0.45 * index) + 0.07 * std::cos(0.25 * index);
    }
    production.previousCoordinates = production.acceptedCoordinates;
    production.referenceCoordinates = production.acceptedCoordinates;
    std::fill(production.shapeWeights.begin(),
              production.shapeWeights.end(), 0.0);
    for (std::size_t sample = 0; sample < 3; ++sample)
    {
        const std::size_t base = sample * 7 * 12;
        for (std::size_t local = 0; local < 12; ++local)
            production.shapeWeights[base + local] = 1.0 / 12.0;
        const double vScale = 0.8 + 0.3 * static_cast<double>(sample);
        const double wScale = 0.7 + 0.2 * static_cast<double>(sample);
        production.shapeWeights[base + 12] = -vScale;
        production.shapeWeights[base + 13] = vScale;
        production.shapeWeights[base + 24] = -wScale;
        production.shapeWeights[base + 26] = wScale;
    }
    fixtures.push_back({"production_cpu", production,
                        production.acceptedCoordinates});
    return fixtures;
}

double max_abs_error(const GeometryCandidateResult &actual,
                     const detail::RegularGeometryCpuResult &expected)
{
    if (actual.faceAreas.size() != expected.faceAreas.size() ||
        actual.faceVolumes.size() != expected.faceVolumes.size())
        return std::numeric_limits<double>::infinity();
    double error = std::max(std::abs(actual.totalArea - expected.totalArea),
                            std::abs(actual.totalVolume - expected.totalVolume));
    for (std::size_t face = 0; face < expected.faceAreas.size(); ++face)
        error = std::max(
            error,
            std::max(std::abs(actual.faceAreas[face] - expected.faceAreas[face]),
                     std::abs(actual.faceVolumes[face] - expected.faceVolumes[face])));
    return error;
}

bool same_bytes(const std::vector<double> &left,
                const std::vector<double> &right)
{
    return left.size() == right.size() &&
           (left.empty() || std::memcmp(left.data(), right.data(),
                                       left.size() * sizeof(double)) == 0);
}

CaseResult run_case(const GeometryFixture &fixture, int device, int iterations)
{
    CaseResult result;
    result.name = fixture.name;
    DeviceStateConfig config;
    config.deviceOrdinal = device;
    auto created = create_cuda_mesh_state(fixture.pack, config);
    result.createError = created.report.error;
    if (!created.ok())
    {
        result.finalReport = created.report;
        return result;
    }
    result.created = true;
    result.warmedAllocations = created.state->report().successfulAllocations;
    const detail::RegularGeometryCpuResult expected =
        detail::evaluate_regular_geometry_cpu(fixture.pack, fixture.candidate);
    for (int iteration = 0; iteration < iterations; ++iteration)
    {
        const std::uint64_t generation =
            created.state->report().residentGenerations.acceptedCoordinates + 1;
        result.transitions = created.state->prepare_candidate(
            fixture.candidate, generation).ok();
        if (!result.transitions)
            break;
        const GeometryCandidateResult geometry =
            created.state->compute_candidate_geometry();
        result.transitions = geometry.ok();
        if (!result.transitions)
            break;
        result.maxAbsError = std::max(result.maxAbsError,
                                      max_abs_error(geometry, expected));
        if (iteration == 0)
        {
            result.firstAreas = geometry.faceAreas;
            result.firstVolumes = geometry.faceVolumes;
            result.firstTotalArea = geometry.totalArea;
            result.firstTotalVolume = geometry.totalVolume;
        }
        else
        {
            result.repeatable = result.repeatable &&
                same_bytes(result.firstAreas, geometry.faceAreas) &&
                same_bytes(result.firstVolumes, geometry.faceVolumes) &&
                std::memcmp(&result.firstTotalArea, &geometry.totalArea,
                            sizeof(double)) == 0 &&
                std::memcmp(&result.firstTotalVolume, &geometry.totalVolume,
                            sizeof(double)) == 0;
        }
        if (iteration % 2 == 0)
        {
            result.transitions = created.state->commit().ok();
            ++result.commits;
        }
        else
        {
            result.transitions = created.state->rollback().ok();
            ++result.rollbacks;
        }
        if (!result.transitions)
            break;
    }
    result.cpuParity = result.maxAbsError <= kTolerance;
    if (fixture.name == "boundary_ghost")
        result.ghostZero = result.firstAreas.size() == 2 &&
                           result.firstVolumes.size() == 2 &&
                           result.firstAreas[1] == 0.0 &&
                           result.firstVolumes[1] == 0.0;
    if (fixture.name == "degenerate")
        result.degenerateZero = result.firstTotalArea == 0.0 &&
                                result.firstTotalVolume == 0.0;
    result.activeReport = created.state->report();
    const bool noWarmAllocations =
        result.activeReport.successfulAllocations == result.warmedAllocations;
    const DeviceStateError closed = created.state->close();
    result.finalReport = created.state->report();
    result.transitions = result.transitions && noWarmAllocations && closed.ok() &&
                         static_cast<int>(result.commits + result.rollbacks) ==
                             iterations;
    return result;
}

std::string json_string(const std::string &value)
{
    std::ostringstream output;
    output << '"';
    for (const char character : value)
    {
        if (character == '"' || character == '\\')
            output << '\\';
        if (character == '\n')
            output << "\\n";
        else
            output << character;
    }
    output << '"';
    return output.str();
}

int integer_argument(char **argv, int argc, const std::string &name,
                     int fallback)
{
    for (int index = 1; index + 1 < argc; ++index)
        if (argv[index] == name)
            return std::atoi(argv[index + 1]);
    return fallback;
}

} // namespace

int main(int argc, char **argv)
{
    const int device = integer_argument(argv, argc, "--device", 0);
    const int iterations = integer_argument(argv, argc, "--iterations", 20);
    std::vector<CaseResult> cases;
    for (const GeometryFixture &fixture : make_fixtures())
    {
        cases.push_back(run_case(fixture, device, iterations));
        if (!cases.back().created)
        {
            const DeviceStateReport &report = cases.back().finalReport;
            std::cout << "{\"status\":\"unavailable\",\"compiled\":"
                      << (report.compiled ? "true" : "false")
                      << ",\"available\":false,\"error_code\":"
                      << json_string(device_state_error_code_name(
                             report.error.code))
                      << ",\"operation\":" << json_string(report.error.operation)
                      << ",\"message\":" << json_string(report.error.message)
                      << "}\n";
            return report.compiled ? 77 : 0;
        }
    }

    const CaseResult &natural = cases[0];
    CaseResult &permuted = cases[1];
    permuted.permutationEqual =
        same_bytes(natural.firstAreas, permuted.firstAreas) &&
        same_bytes(natural.firstVolumes, permuted.firstVolumes) &&
        std::memcmp(&natural.firstTotalArea, &permuted.firstTotalArea,
                    sizeof(double)) == 0 &&
        std::memcmp(&natural.firstTotalVolume, &permuted.firstTotalVolume,
                    sizeof(double)) == 0;

    bool pass = true;
    bool geometryRepeatable = true;
    bool transfersComplete = true;
    bool noWarmAllocations = true;
    bool allocationFreeBalance = true;
    bool closed = true;
    bool cleanupPending = false;
    double geometryMaxAbsError = 0.0;
    std::uint64_t commits = 0, rollbacks = 0, allocationEpoch = 0;
    std::uint64_t transactionEpoch = 0, warmedAllocations = 0;
    std::uint64_t finalAllocations = 0, successfulFrees = 0;
    std::size_t residentBytes = 0, finalResidentBytes = 0;
    std::size_t memoryBudgetBytes = 0;
    std::vector<TransferCounter> transfers(
        static_cast<std::size_t>(TransferReason::Count));
    for (const CaseResult &item : cases)
    {
        pass = pass && item.pass();
        geometryRepeatable = geometryRepeatable && item.repeatable;
        geometryMaxAbsError = std::max(geometryMaxAbsError, item.maxAbsError);
        commits += item.commits;
        rollbacks += item.rollbacks;
        allocationEpoch += item.activeReport.allocationEpoch;
        transactionEpoch += item.activeReport.transactionEpoch;
        warmedAllocations += item.warmedAllocations;
        finalAllocations += item.finalReport.successfulAllocations;
        successfulFrees += item.finalReport.successfulFrees;
        residentBytes = std::max(residentBytes, item.activeReport.residentBytes);
        finalResidentBytes += item.finalReport.residentBytes;
        memoryBudgetBytes = std::max(
            memoryBudgetBytes, item.activeReport.lastMemoryBudgetBytes);
        noWarmAllocations = noWarmAllocations &&
            item.activeReport.successfulAllocations == item.warmedAllocations;
        allocationFreeBalance = allocationFreeBalance &&
            item.finalReport.successfulAllocations ==
                item.finalReport.successfulFrees;
        closed = closed && item.finalReport.phase == TransactionPhase::Closed;
        cleanupPending = cleanupPending || item.finalReport.cleanupPending;
        for (std::size_t reason = 0; reason < transfers.size(); ++reason)
        {
            const TransferCounter &source = item.activeReport.transfers[reason];
            transfersComplete = transfersComplete &&
                source.attemptedOperations == source.completedOperations &&
                source.attemptedBytes == source.completedBytes;
            transfers[reason].completedOperations += source.completedOperations;
            transfers[reason].completedBytes += source.completedBytes;
        }
    }
    pass = pass && geometryMaxAbsError <= kTolerance && geometryRepeatable &&
           transfersComplete && noWarmAllocations && allocationFreeBalance &&
           closed && !cleanupPending && finalResidentBytes == 0;

    std::cout << "{\"status\":" << json_string(pass ? "pass" : "fail")
              << ",\"compiled\":true,\"available\":true"
              << ",\"device_ordinal\":" << device
              << ",\"iterations\":" << iterations
              << ",\"case_count\":" << cases.size()
              << ",\"total_transactions\":" << commits + rollbacks
              << ",\"commits\":" << commits
              << ",\"rollbacks\":" << rollbacks
              << ",\"allocation_epoch\":" << allocationEpoch
              << ",\"transaction_epoch\":" << transactionEpoch
              << ",\"warmed_allocations\":" << warmedAllocations
              << ",\"final_allocations\":" << finalAllocations
              << ",\"successful_frees\":" << successfulFrees
              << ",\"allocation_free_balance\":"
              << (allocationFreeBalance ? "true" : "false")
              << ",\"no_warm_allocations\":"
              << (noWarmAllocations ? "true" : "false")
              << ",\"geometry_max_abs_error\":" << std::setprecision(17)
              << geometryMaxAbsError
              << ",\"geometry_repeatable\":"
              << (geometryRepeatable ? "true" : "false")
              << ",\"resident_bytes\":" << residentBytes
              << ",\"final_resident_bytes\":" << finalResidentBytes
              << ",\"closed\":" << (closed ? "true" : "false")
              << ",\"cleanup_pending\":"
              << (cleanupPending ? "true" : "false")
              << ",\"cleanup_error_code\":\"none\""
              << ",\"memory_budget_bytes\":" << memoryBudgetBytes
              << ",\"transfers_complete\":"
              << (transfersComplete ? "true" : "false")
              << ",\"geometry_cases\":{";
    for (std::size_t index = 0; index < cases.size(); ++index)
    {
        if (index)
            std::cout << ',';
        const CaseResult &item = cases[index];
        std::cout << json_string(item.name)
                  << ":{\"pass\":" << (item.pass() ? "true" : "false")
                  << ",\"cpu_parity\":"
                  << (item.cpuParity ? "true" : "false")
                  << ",\"repeatable\":"
                  << (item.repeatable ? "true" : "false")
                  << ",\"max_abs_error\":" << item.maxAbsError
                  << ",\"ghost_zero\":"
                  << (item.ghostZero ? "true" : "false")
                  << ",\"degenerate_zero\":"
                  << (item.degenerateZero ? "true" : "false")
                  << ",\"permutation_equal\":"
                  << (item.permutationEqual ? "true" : "false") << '}';
    }
    std::cout << "},\"transfers\":{";
    for (std::size_t reason = 0; reason < transfers.size(); ++reason)
    {
        if (reason)
            std::cout << ',';
        std::cout << json_string(transfer_reason_name(
                         static_cast<TransferReason>(reason)))
                  << ":{\"operations\":"
                  << transfers[reason].completedOperations
                  << ",\"bytes\":" << transfers[reason].completedBytes << '}';
    }
    std::cout << "}}\n";
    return pass ? 0 : 1;
}
