#include "cuda/Cuda_mesh_state.hpp"

#include <cstdlib>
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
    pack.shapeWeights.assign(252, 0.125);
    for (int value = 0; value < 36; ++value)
    {
        pack.acceptedCoordinates.push_back(value * 0.25);
        pack.previousCoordinates.push_back(value * 0.25 - 0.01);
        pack.referenceCoordinates.push_back(value * 0.25 + 0.01);
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
    std::vector<double> candidate(36, 0.0);
    bool transitionsOk = true;
    std::uint64_t commits = 0, rollbacks = 0;
    for (int iteration = 0; iteration < iterations; ++iteration)
    {
        for (std::size_t index = 0; index < candidate.size(); ++index)
            candidate[index] = iteration + index * 0.001;
        const std::uint64_t generation =
            created.state->report().residentGenerations.acceptedCoordinates + 1;
        transitionsOk = transitionsOk &&
                        created.state->prepare_candidate(candidate, generation).ok() &&
                        created.state->mark_computing().ok();
        if (!transitionsOk)
            break;
        if (iteration % 2 == 0)
        {
            transitionsOk = created.state->mark_validated().ok() &&
                            created.state->commit().ok();
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

    const DeviceStateReport report = created.state->report();
    bool transfersComplete = true;
    for (const auto &counter : report.transfers)
        transfersComplete = transfersComplete &&
                            counter.attemptedOperations ==
                                counter.completedOperations &&
                            counter.attemptedBytes == counter.completedBytes;
    const bool noWarmAllocations =
        report.successfulAllocations == warmedAllocations;
    const bool pass = transitionsOk && noWarmAllocations && transfersComplete &&
                      report.phase == TransactionPhase::IdleAccepted &&
                      static_cast<int>(commits + rollbacks) == iterations;

    std::cout << "{\"status\":" << json_string(pass ? "pass" : "fail")
              << ",\"compiled\":true,\"available\":true"
              << ",\"device_ordinal\":" << device
              << ",\"iterations\":" << iterations
              << ",\"commits\":" << commits
              << ",\"rollbacks\":" << rollbacks
              << ",\"allocation_epoch\":" << report.allocationEpoch
              << ",\"transaction_epoch\":" << report.transactionEpoch
              << ",\"warmed_allocations\":" << warmedAllocations
              << ",\"final_allocations\":" << report.successfulAllocations
              << ",\"no_warm_allocations\":"
              << (noWarmAllocations ? "true" : "false")
              << ",\"resident_bytes\":" << report.residentBytes
              << ",\"memory_budget_bytes\":" << report.lastMemoryBudgetBytes
              << ",\"transfers_complete\":"
              << (transfersComplete ? "true" : "false")
              << ",\"transfers\":{";
    for (std::size_t reason = 0; reason < report.transfers.size(); ++reason)
    {
        if (reason)
            std::cout << ',';
        const auto transferReason = static_cast<TransferReason>(reason);
        const auto &counter = report.transfers[reason];
        std::cout << json_string(transfer_reason_name(transferReason))
                  << ":{\"operations\":" << counter.completedOperations
                  << ",\"bytes\":" << counter.completedBytes << '}';
    }
    std::cout << "}}\n";
    return pass ? 0 : 1;
}
