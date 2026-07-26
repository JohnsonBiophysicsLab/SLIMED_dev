#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <vector>

#include <gtest/gtest.h>

#include "energy_force/Source_keyed_kernel_call.hpp"

namespace
{
using namespace slimed::source_keyed_kernel;

SourceKeyedKernelCallInput make_valid_input()
{
    SourceKeyedKernelCallInput input;
    input.sourceCount = 3;
    input.mappings.push_back(
        SourceMappingView{0, {{0, 1, 2}}, {2, 0, 1}, true});

    SourceKeyedFaceRows faceRows;
    faceRows.faceIndex = 0;
    faceRows.orientedFaceVertices = {{0, 1, 2}};
    faceRows.samples.resize(1);
    for (int row = 0; row < kDerivativeRowCount; ++row)
    {
        SourceKeyedRow &target = faceRows.samples[0].rows[row];
        target.sourceIds = {2, 0, 1};
        const double rowValue = row == 6 ? 5.0 : static_cast<double>(row);
        target.coefficients = {
            rowValue + 0.25, rowValue + 0.5, rowValue + 0.75};
    }
    input.rows.push_back(faceRows);

    SourceKeyedFaceForces faceForces;
    faceForces.faceIndex = 0;
    faceForces.sourceIds = {2, 0, 1};
    faceForces.forces.resize(3);
    for (std::size_t position = 0;
         position < faceForces.sourceIds.size();
         ++position)
    {
        const int sourceId = faceForces.sourceIds[position];
        for (int kind = 0; kind < kForceKindCount; ++kind)
        {
            for (int axis = 0; axis < kAxisCount; ++axis)
            {
                faceForces.forces[position][kind][axis] =
                    100.0 * sourceId + 10.0 * kind + axis + 0.125;
            }
        }
    }
    input.forces.push_back(faceForces);
    return input;
}

void expect_same_prepared(const PreparedSourceKeyedKernelCall &left,
                          const PreparedSourceKeyedKernelCall &right)
{
    ASSERT_EQ(left.sourceCount, right.sourceCount);
    ASSERT_EQ(left.faces.size(), right.faces.size());
    for (std::size_t face = 0; face < left.faces.size(); ++face)
    {
        const PreparedSourceKeyedFace &leftFace = left.faces[face];
        const PreparedSourceKeyedFace &rightFace = right.faces[face];
        EXPECT_EQ(leftFace.mapping.faceIndex, rightFace.mapping.faceIndex);
        EXPECT_EQ(leftFace.mapping.orientedFaceVertices,
                  rightFace.mapping.orientedFaceVertices);
        EXPECT_EQ(leftFace.mapping.originalSourceIds,
                  rightFace.mapping.originalSourceIds);
        ASSERT_EQ(leftFace.samples.size(), rightFace.samples.size());
        for (std::size_t sample = 0;
             sample < leftFace.samples.size();
             ++sample)
        {
            for (int row = 0; row < kDerivativeRowCount; ++row)
            {
                EXPECT_EQ(leftFace.samples[sample].rows[row].sourceIds,
                          rightFace.samples[sample].rows[row].sourceIds);
                EXPECT_EQ(leftFace.samples[sample].rows[row].coefficients,
                          rightFace.samples[sample].rows[row].coefficients);
            }
        }
        EXPECT_EQ(leftFace.forces, rightFace.forces);
    }
}

template <typename Mutation>
void expect_rejected(Mutation mutation)
{
    SourceKeyedKernelCallInput input = make_valid_input();
    mutation(input);
    EXPECT_THROW(prepare_source_keyed_kernel_call(input),
                 std::invalid_argument);
}
} // namespace

TEST(SourceKeyedKernelCallTest,
     CanonicalizesPermutationAndDuplicateDerivativeRowsWithoutInputMutation)
{
    SourceKeyedKernelCallInput baseline = make_valid_input();
    const std::vector<int> originalMappingOrder =
        baseline.mappings[0].originalSourceIds;
    const PreparedSourceKeyedKernelCall prepared =
        prepare_source_keyed_kernel_call(baseline);

    SourceKeyedKernelCallInput permuted = baseline;
    std::reverse(permuted.mappings[0].originalSourceIds.begin(),
                 permuted.mappings[0].originalSourceIds.end());
    for (SourceKeyedRow &row : permuted.rows[0].samples[0].rows)
    {
        std::reverse(row.sourceIds.begin(), row.sourceIds.end());
        std::reverse(row.coefficients.begin(), row.coefficients.end());
    }
    std::reverse(permuted.forces[0].sourceIds.begin(),
                 permuted.forces[0].sourceIds.end());
    std::reverse(permuted.forces[0].forces.begin(),
                 permuted.forces[0].forces.end());
    const PreparedSourceKeyedKernelCall permutedPrepared =
        prepare_source_keyed_kernel_call(permuted);
    expect_same_prepared(prepared, permutedPrepared);

    SourceKeyedKernelCallInput duplicated = baseline;
    for (SourceKeyedRow &row : duplicated.rows[0].samples[0].rows)
    {
        const double half = std::ldexp(row.coefficients[0], -1);
        row.coefficients[0] = half;
        row.sourceIds.push_back(row.sourceIds[0]);
        row.coefficients.push_back(half);
        std::reverse(row.sourceIds.begin(), row.sourceIds.end());
        std::reverse(row.coefficients.begin(), row.coefficients.end());
    }
    const PreparedSourceKeyedKernelCall duplicatePrepared =
        prepare_source_keyed_kernel_call(duplicated);
    expect_same_prepared(prepared, duplicatePrepared);

    EXPECT_EQ(baseline.mappings[0].originalSourceIds,
              originalMappingOrder);
    EXPECT_EQ(prepared.faces[0].mapping.originalSourceIds,
              (std::vector<int>{0, 1, 2}));
}

TEST(SourceKeyedKernelCallTest,
     AccumulatesWithAnIndependentFixedIndexForceOracle)
{
    SourceKeyedKernelCallInput input = make_valid_input();
    SourceKeyedKernelCallInput second = make_valid_input();
    second.mappings[0].faceIndex = 1;
    second.rows[0].faceIndex = 1;
    second.forces[0].faceIndex = 1;
    input.mappings.push_back(second.mappings[0]);
    input.rows.push_back(second.rows[0]);
    input.forces.push_back(second.forces[0]);

    const PreparedSourceKeyedKernelCall prepared =
        prepare_source_keyed_kernel_call(input);
    const std::vector<SourceForceKinds> accumulated =
        accumulate_source_keyed_force_contributions(prepared);
    ASSERT_EQ(accumulated.size(), 3u);

    std::array<std::array<long double, 9>, 3> oracle{};
    for (const SourceKeyedFaceForces &face : input.forces)
    {
        for (std::size_t position = 0;
             position < face.sourceIds.size();
             ++position)
        {
            const int sourceId = face.sourceIds[position];
            for (int kind = 0; kind < 3; ++kind)
            {
                for (int axis = 0; axis < 3; ++axis)
                {
                    const int fixedIndex = kind * 3 + axis;
                    oracle[sourceId][fixedIndex] +=
                        static_cast<long double>(
                            face.forces[position][kind][axis]);
                }
            }
        }
    }
    for (int source = 0; source < 3; ++source)
    {
        for (int kind = 0; kind < 3; ++kind)
        {
            for (int axis = 0; axis < 3; ++axis)
            {
                EXPECT_DOUBLE_EQ(
                    accumulated[source][kind][axis],
                    static_cast<double>(
                        oracle[source][kind * 3 + axis]));
            }
        }
    }
}

TEST(SourceKeyedKernelCallTest, RejectsMalformedRequestsBeforeReturningOutput)
{
    expect_rejected([](auto &input) { input.sourceCount = 0; });
    expect_rejected(
        [](auto &input) { input.rows[0].faceIndex = 1; });
    expect_rejected([](auto &input) {
        std::swap(input.rows[0].orientedFaceVertices[1],
                  input.rows[0].orientedFaceVertices[2]);
    });
    expect_rejected(
        [](auto &input) { input.mappings[0].productionOneRingEmpty = false; });
    expect_rejected([](auto &input) {
        input.mappings[0].originalSourceIds[1] =
            input.mappings[0].originalSourceIds[0];
    });
    expect_rejected([](auto &input) {
        input.rows[0].samples[0].rows[0].coefficients.pop_back();
    });
    expect_rejected([](auto &input) {
        input.rows[0].samples[0].rows[0].sourceIds.pop_back();
        input.rows[0].samples[0].rows[0].coefficients.pop_back();
    });
    expect_rejected([](auto &input) {
        input.rows[0].samples[0].rows[0].coefficients[0] =
            std::numeric_limits<double>::infinity();
    });
    expect_rejected([](auto &input) {
        input.rows[0].samples[0].rows[6].coefficients[0] += 1.0;
    });
    expect_rejected([](auto &input) {
        input.forces[0].sourceIds[1] = input.forces[0].sourceIds[0];
    });
    expect_rejected([](auto &input) {
        input.forces[0].forces[0][0][0] =
            std::numeric_limits<double>::quiet_NaN();
    });
}
