#pragma once

#include "energy_force/Source_keyed_kernel_call.hpp"

// Preserve the proof package's local type names while executing the production
// backend-neutral helper introduced by the successor lane.
namespace valence4_source_keyed_proof
{
using slimed::source_keyed_kernel::PreparedSourceKeyedFace;
using slimed::source_keyed_kernel::PreparedSourceKeyedKernelCall;
using slimed::source_keyed_kernel::SourceForceComponentBuffer;
using slimed::source_keyed_kernel::SourceForceKinds;
using slimed::source_keyed_kernel::SourceKeyedFaceForces;
using slimed::source_keyed_kernel::SourceKeyedFaceRows;
using slimed::source_keyed_kernel::SourceKeyedKernelCallInput;
using slimed::source_keyed_kernel::SourceKeyedRow;
using slimed::source_keyed_kernel::SourceKeyedSampleRows;
using slimed::source_keyed_kernel::SourceMappingView;
using slimed::source_keyed_kernel::Vec3;
using slimed::source_keyed_kernel::accumulate_source_keyed_force_contributions;
using slimed::source_keyed_kernel::kAxisCount;
using slimed::source_keyed_kernel::kDerivativeRowCount;
using slimed::source_keyed_kernel::kForceComponentsPerSource;
using slimed::source_keyed_kernel::kForceKindCount;
using slimed::source_keyed_kernel::prepare_source_keyed_kernel_call;
using slimed::source_keyed_kernel::reduce_source_keyed_force_component_buffers;
using slimed::source_keyed_kernel::
    scatter_source_keyed_face_forces_to_component_buffer;
} // namespace valence4_source_keyed_proof
