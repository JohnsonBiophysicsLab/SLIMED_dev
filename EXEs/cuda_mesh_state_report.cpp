#include "cuda/Cuda_mesh_state.hpp"

#include <cstdlib>
#include <algorithm>
#include <cmath>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace
{
using namespace slimed::cuda_residency;

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
    for (int source = 0; source < 12; ++source)
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
    for (int source = 0; source < 3; ++source)
        for (int axis = 0; axis < 3; ++axis)
            pack.acceptedCoordinates[source * 3 + axis] =
                pack.previousCoordinates[source * 3 + axis] =
                    pack.referenceCoordinates[source * 3 + axis] =
                        controls[source][axis];
    for (int sample = 0; sample < 3; ++sample)
    {
        const int base = sample * 7 * 12;
        pack.shapeWeights[base] = 1.0;
        pack.shapeWeights[base + 12] = -1.0;
        pack.shapeWeights[base + 13] = 1.0;
        pack.shapeWeights[base + 24] = -1.0;
        pack.shapeWeights[base + 26] = 1.0;
    }
    pack.parameters.kCurv = 1.0;
    return pack;
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
    DeviceStateConfig config;
    config.deviceOrdinal = device;
    auto created = create_cuda_mesh_state(make_pack(), config);
    if (!created.ok())
    {
        std::cout << "{\"status\":\"unavailable\",\"compiled\":"
                  << (created.report.compiled ? "true" : "false")
                  << ",\"available\":false,\"error_code\":"
                  << json_string(device_state_error_code_name(
                         created.report.error.code))
                  << ",\"operation\":"
                  << json_string(created.report.error.operation)
                  << ",\"message\":"
                  << json_string(created.report.error.message) << "}\n";
        return created.report.compiled ? 77 : 0;
    }

    const std::uint64_t warmedAllocations =
        created.state->report().successfulAllocations;
    const std::vector<double> candidate = make_pack().acceptedCoordinates;
    bool transitionsOk = true;
    bool geometryRepeatable = true;
    double geometryMaxAbsError = 0.0;
    std::vector<double> firstAreas, firstVolumes;
    double firstTotalArea = 0.0, firstTotalVolume = 0.0;
    std::uint64_t commits = 0, rollbacks = 0;
    for (int iteration = 0; iteration < iterations; ++iteration)
    {
        const std::uint64_t generation =
            created.state->report().residentGenerations.acceptedCoordinates + 1;
        transitionsOk = transitionsOk &&
                        created.state->prepare_candidate(candidate, generation).ok();
        if (!transitionsOk)
            break;
        const GeometryCandidateResult geometry =
            created.state->compute_candidate_geometry();
        transitionsOk = geometry.ok() && geometry.faceAreas.size() == 1 &&
                        geometry.faceVolumes.size() == 1;
        if (!transitionsOk)
            break;
        geometryMaxAbsError = std::max(
            geometryMaxAbsError,
            std::max(std::abs(geometry.faceAreas[0] - 0.5),
                     std::abs(geometry.faceVolumes[0] - 0.33333333332)));
        geometryMaxAbsError = std::max(
            geometryMaxAbsError,
            std::max(std::abs(geometry.totalArea - 0.5),
                     std::abs(geometry.totalVolume - 0.33333333332)));
        if (iteration == 0)
        {
            firstAreas = geometry.faceAreas;
            firstVolumes = geometry.faceVolumes;
            firstTotalArea = geometry.totalArea;
            firstTotalVolume = geometry.totalVolume;
        }
        else
        {
            geometryRepeatable = geometryRepeatable &&
                std::memcmp(firstAreas.data(), geometry.faceAreas.data(),
                            sizeof(double)) == 0 &&
                std::memcmp(firstVolumes.data(), geometry.faceVolumes.data(),
                            sizeof(double)) == 0 &&
                std::memcmp(&firstTotalArea, &geometry.totalArea,
                            sizeof(double)) == 0 &&
                std::memcmp(&firstTotalVolume, &geometry.totalVolume,
                            sizeof(double)) == 0;
        }
        if (iteration % 2 == 0)
        {
            transitionsOk = created.state->commit().ok();
            ++commits;
        }
        else
        {
            transitionsOk = created.state->rollback().ok();
            ++rollbacks;
        }
        if (!transitionsOk)
            break;
    }

    const DeviceStateReport activeReport = created.state->report();
    bool transfersComplete = true;
    for (const auto &counter : activeReport.transfers)
        transfersComplete = transfersComplete &&
                            counter.attemptedOperations ==
                                counter.completedOperations &&
                            counter.attemptedBytes == counter.completedBytes;
    const bool noWarmAllocations =
        activeReport.successfulAllocations == warmedAllocations;
    const DeviceStateError closeResult = created.state->close();
    const DeviceStateReport finalReport = created.state->report();
    const bool allocationFreeBalance =
        finalReport.successfulAllocations == finalReport.successfulFrees;
    const bool cleanupComplete =
        closeResult.ok() && finalReport.phase == TransactionPhase::Closed &&
        !finalReport.cleanupPending && finalReport.cleanupError.ok() &&
        finalReport.residentBytes == 0 && allocationFreeBalance;
    const bool geometryParity = geometryMaxAbsError <= 1.0e-12;
    const bool pass = transitionsOk && geometryParity && geometryRepeatable &&
                      noWarmAllocations && transfersComplete &&
                      activeReport.phase == TransactionPhase::IdleAccepted &&
                      cleanupComplete &&
                      static_cast<int>(commits + rollbacks) == iterations;

    std::cout << "{\"status\":" << json_string(pass ? "pass" : "fail")
              << ",\"compiled\":true,\"available\":true"
              << ",\"device_ordinal\":" << device
              << ",\"iterations\":" << iterations
              << ",\"commits\":" << commits
              << ",\"rollbacks\":" << rollbacks
              << ",\"allocation_epoch\":" << activeReport.allocationEpoch
              << ",\"transaction_epoch\":" << activeReport.transactionEpoch
              << ",\"warmed_allocations\":" << warmedAllocations
              << ",\"final_allocations\":" << finalReport.successfulAllocations
              << ",\"successful_frees\":" << finalReport.successfulFrees
              << ",\"allocation_free_balance\":"
              << (allocationFreeBalance ? "true" : "false")
              << ",\"no_warm_allocations\":"
              << (noWarmAllocations ? "true" : "false")
              << ",\"geometry_max_abs_error\":"
              << std::setprecision(17) << geometryMaxAbsError
              << ",\"geometry_repeatable\":"
              << (geometryRepeatable ? "true" : "false")
              << ",\"resident_bytes\":" << activeReport.residentBytes
              << ",\"final_resident_bytes\":" << finalReport.residentBytes
              << ",\"closed\":"
              << (finalReport.phase == TransactionPhase::Closed ? "true" : "false")
              << ",\"cleanup_pending\":"
              << (finalReport.cleanupPending ? "true" : "false")
              << ",\"cleanup_error_code\":"
              << json_string(device_state_error_code_name(
                     finalReport.cleanupError.code))
              << ",\"memory_budget_bytes\":"
              << activeReport.lastMemoryBudgetBytes
              << ",\"transfers_complete\":"
              << (transfersComplete ? "true" : "false")
              << ",\"transfers\":{";
    for (std::size_t reason = 0; reason < activeReport.transfers.size(); ++reason)
    {
        if (reason)
            std::cout << ',';
        const auto transferReason = static_cast<TransferReason>(reason);
        const auto &counter = activeReport.transfers[reason];
        std::cout << json_string(transfer_reason_name(transferReason))
                  << ":{\"operations\":" << counter.completedOperations
                  << ",\"bytes\":" << counter.completedBytes << '}';
    }
    std::cout << "}}\n";
    return pass ? 0 : 1;
}
