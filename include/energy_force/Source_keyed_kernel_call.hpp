/**
 * @file Source_keyed_kernel_call.hpp
 * @brief Backend-neutral preparation for variable-cardinality force kernels.
 */

#pragma once

#include <array>
#include <vector>

class Mesh;

namespace slimed::source_keyed_kernel
{
constexpr int kDerivativeRowCount = 7;
constexpr int kForceKindCount = 3;
constexpr int kAxisCount = 3;
constexpr int kForceComponentsPerSource = kForceKindCount * kAxisCount;

using Vec3 = std::array<double, kAxisCount>;
using SourceForceKinds = std::array<Vec3, kForceKindCount>;
using SourceForceComponentBuffer = std::vector<double>;

struct SourceMappingView
{
    int faceIndex = -1;
    std::array<int, 3> orientedFaceVertices{{-1, -1, -1}};
    std::vector<int> originalSourceIds;
    bool productionOneRingEmpty = false;
};

struct SourceKeyedRow
{
    std::vector<int> sourceIds;
    std::vector<double> coefficients;
};

struct SourceKeyedSampleRows
{
    std::array<SourceKeyedRow, kDerivativeRowCount> rows;
};

struct SourceKeyedFaceRows
{
    int faceIndex = -1;
    std::array<int, 3> orientedFaceVertices{{-1, -1, -1}};
    std::vector<SourceKeyedSampleRows> samples;
};

struct SourceKeyedFaceForces
{
    int faceIndex = -1;
    std::vector<int> sourceIds;
    std::vector<SourceForceKinds> forces;
};

struct SourceKeyedKernelCallInput
{
    int sourceCount = 0;
    std::vector<SourceMappingView> mappings;
    std::vector<SourceKeyedFaceRows> rows;
    std::vector<SourceKeyedFaceForces> forces;
};

struct PreparedSourceKeyedFace
{
    SourceMappingView mapping;
    std::vector<SourceKeyedSampleRows> samples;
    std::vector<SourceForceKinds> forces;
};

struct PreparedSourceKeyedKernelCall
{
    int sourceCount = 0;
    std::vector<PreparedSourceKeyedFace> faces;
};

/**
 * Validate and canonicalize a complete variable-cardinality kernel request.
 *
 * The function returns a new owned result only after every face, derivative
 * row, and force contribution has passed validation. It does not mutate the
 * request, Mesh state, Face::oneRingVertices, vertex forces, or thread buffers.
 */
PreparedSourceKeyedKernelCall prepare_source_keyed_kernel_call(
    const SourceKeyedKernelCallInput &input);

/**
 * Accumulate prepared force contributions by original source ID.
 *
 * The returned vector is owned by the caller. No production Mesh or OpenMP
 * storage is consulted or mutated.
 */
std::vector<SourceForceKinds> accumulate_source_keyed_force_contributions(
    const PreparedSourceKeyedKernelCall &prepared);

/**
 * Scatter one canonical face contribution into a caller-owned production-
 * shaped source force buffer.
 *
 * The buffer layout is source, force kind, then axis, matching the current
 * nVertices * 9 production thread buffers. The function validates the entire
 * face and destination before publishing an updated buffer.
 */
void scatter_source_keyed_face_forces_to_component_buffer(
    const PreparedSourceKeyedFace &face,
    int sourceCount,
    SourceForceComponentBuffer &componentBuffer);

/**
 * Reduce caller-owned source force buffers in ascending buffer order.
 *
 * This mirrors the current production thread-buffer reduction shape without
 * consulting OpenMP state or mutating Mesh/Vertex storage.
 */
std::vector<SourceForceKinds> reduce_source_keyed_force_component_buffers(
    const std::vector<SourceForceComponentBuffer> &componentBuffers,
    int sourceCount);

/**
 * Publish reduced source-keyed membrane forces to matching Mesh vertices.
 *
 * The complete source vector and every destination are validated before the
 * first write. Publication overwrites only forceCurvature, forceArea, and
 * forceVolume; it does not update forceTotal or any other Mesh state.
 */
void publish_source_keyed_membrane_forces_to_vertices(
    const std::vector<SourceForceKinds> &sourceForces,
    Mesh &mesh);
} // namespace slimed::source_keyed_kernel
