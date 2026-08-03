/**
 * @file Guarded_source_keyed_production_face_loop.hpp
 * @brief Internal validated entry into the source-keyed membrane face loop.
 */

#pragma once

#include "energy_force/Source_keyed_kernel_call.hpp"

#include <vector>

class Mesh;

namespace slimed::guarded_source_keyed_face_loop
{
struct GuardedFaceGeometry
{
    int faceIndex = -1;
    double elementArea = 0.0;
    double elementVolume = 0.0;
};

/** Validate the complete transaction and all production destinations. */
void validate_guarded_source_keyed_production_face_loop(
    const Mesh &mesh,
    const std::vector<GuardedFaceGeometry> &geometry,
    double totalArea,
    double totalVolume,
    const source_keyed_kernel::PreparedSourceKeyedKernelCall &prepared);

/**
 * Execute a fully validated source-keyed membrane transaction.
 *
 * The complete topology-independent row package, face/global geometry, and
 * production destinations are validated before the first Mesh write. Callers
 * remain responsible for their topology, dependency, runtime, and scientific
 * gates. This internal seam does not select or enable a default route.
 */
void execute_guarded_source_keyed_production_face_loop(
    Mesh &mesh,
    const std::vector<GuardedFaceGeometry> &geometry,
    double totalArea,
    double totalVolume,
    const source_keyed_kernel::PreparedSourceKeyedKernelCall &prepared);
} // namespace slimed::guarded_source_keyed_face_loop
